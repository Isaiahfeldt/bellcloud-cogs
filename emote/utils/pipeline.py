# File: emote/utils/pipeline.py (Refactored)

import asyncio
import hashlib
import inspect
import time
import traceback
from typing import Optional

from .effects import Emote, initialize

# Define groups of effects that cannot be used together
CONFLICT_GROUPS = [
    # Example: {"speed", "fast", "slow"},
]


# === EFFECTS CACHE INTEGRATION ===

def filter_visual_effects(queued_effects: list) -> list:
    """
    Filter out non-visual effects from the queued effects list.
    
    Args:
        queued_effects: List of (effect_name, effect_args) tuples
        
    Returns:
        list: Filtered list containing only visual effects
    """
    NON_VISUAL_EFFECTS = {"train", "debug", "latency"}
    return [effect for effect in queued_effects if effect[0] not in NON_VISUAL_EFFECTS]


def has_visual_effects(queued_effects: list) -> bool:
    """
    Check if the queued effects contain any visual effects.
    
    Args:
        queued_effects: List of (effect_name, effect_args) tuples
        
    Returns:
        bool: True if there are visual effects, False otherwise
    """
    visual_effects = filter_visual_effects(queued_effects)
    return len(visual_effects) > 0


async def check_effects_cache(cog_instance, emote: Emote, queued_effects: list) -> Optional[bytes]:
    """
    Check if we have a cached result for this emote + effect combination.
    
    Args:
        cog_instance: The cog instance (for database access)
        emote: The emote object
        queued_effects: List of (effect_name, effect_args) tuples
        
    Returns:
        Optional[bytes]: Cached image data if found, None otherwise
    """
    try:
        from ..slash_commands import db

        # Filter out non-visual effects for cache operations
        visual_effects = filter_visual_effects(queued_effects)

        # If no visual effects remain, skip cache check
        if not visual_effects:
            non_visual_names = [effect[0] for effect in queued_effects]
            print(f"Cache check skipped - only non-visual effects: {non_visual_names}")
            return None

        # Initialize emote to get source image data
        initialized_emote = await initialize(emote)
        if not initialized_emote.img_data:
            return None

        # Create effect combination string using only visual effects
        effect_combination = ','.join([effect[0] for effect in visual_effects])

        # Generate cache key based on visual effects only
        cache_key = db.generate_cache_key(initialized_emote.img_data, effect_combination)
        
        # Debug logging for cache key generation
        source_hash = hashlib.sha256(initialized_emote.img_data).hexdigest()[:16]
        print(f"🔍 Cache Check Debug:")
        print(f"  📋 Original effects: {[effect[0] for effect in queued_effects]}")
        print(f"  ✨ Visual effects only: {[effect[0] for effect in visual_effects]}")
        print(f"  🔑 Effect combination: '{effect_combination}'")
        print(f"  🏷️ Source hash: {source_hash}")
        print(f"  🎯 Cache key: {cache_key}")

        # Check cache
        cached_result = await db.get_cached_effect(cache_key)
        print(f"  🗂️ Database cache lookup result: {'Found' if cached_result else 'Not found'}")
        
        if cached_result:
            cached_file_path = cached_result['cached_file_path']
            cached_url = f"https://media.bellbot.xyz/cache/{cached_file_path}"
            print(f"  📁 Expected cache file path: {cached_file_path}")
            print(f"  🌐 Cache URL: {cached_url}")
            
            # Load cached image data from S3
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(cached_url) as response:
                    print(f"  📡 S3 response status: {response.status}")
                    if response.status == 200:
                        cached_data = await response.read()
                        print(f"  ✅ Cache hit successful! Retrieved {len(cached_data)} bytes")
                        visual_effect_names = [effect[0] for effect in visual_effects]
                        print(f"Cache hit found for visual effects: {visual_effect_names}")
                        return cached_data
                    else:
                        print(f"  ❌ S3 file not accessible, treating as cache miss")

        visual_effect_names = [effect[0] for effect in visual_effects]
        print(f"Cache miss for visual effects: {visual_effect_names}")
        return None
    except Exception as e:
        print(f"Cache check error: {e}")
        return None


async def store_effects_cache(cog_instance, emote: Emote, queued_effects: list,
                              result_image_data: bytes) -> bool:
    """
    Store the processed effect result in cache.
    
    Args:
        cog_instance: The cog instance (for database access)
        emote: The original emote object
        queued_effects: List of (effect_name, effect_args) tuples that were applied
        result_image_data: The processed image data to cache
        
    Returns:
        bool: True if successfully cached, False otherwise
    """
    try:
        from ..slash_commands import db
        import tempfile
        import os

        # CRITICAL FIX: Filter to visual effects only (same as check_effects_cache)
        visual_effects = filter_visual_effects(queued_effects)
        
        # Create effect combination string using only visual effects
        effect_combination = ','.join([effect[0] for effect in visual_effects])

        # CRITICAL FIX: Get the original source emote to match cache check behavior
        # Cache check and storage must use the same source image data for consistent keys
        # We need to get the original emote data that was used in cache check, not the processed result
        
        # Get the original source emote from the pipeline (before any effects were applied)
        # This should match what check_effects_cache used
        from ..slash_commands import db as slash_db
        original_source_emote = await slash_db.get_emote(emote.name, emote.guild_id, False)
        if not original_source_emote:
            print("  ❌ Could not retrieve original source emote for cache key generation")
            return False
            
        # Initialize the original source emote to get the same data cache check used
        initialized_source_emote = await initialize(original_source_emote)
        if not initialized_source_emote.img_data:
            print("  ❌ No initialized source image data available for cache storage")
            return False
            
        # Generate cache key using the original source data (same as cache check)
        cache_key = db.generate_cache_key(initialized_source_emote.img_data, effect_combination)
        source_hash = hashlib.sha256(initialized_source_emote.img_data).hexdigest()[:16]
        
        # Debug logging for cache storage
        print(f"💾 Cache Storage Debug:")
        print(f"  📋 Original effects: {[effect[0] for effect in queued_effects]}")
        print(f"  ✨ Visual effects only: {[effect[0] for effect in visual_effects]}")
        print(f"  🔑 Effect combination: '{effect_combination}'")
        print(f"  🏷️ Source hash: {source_hash}")
        print(f"  🎯 Cache key: {cache_key}")

        # Determine file extension from original
        file_ext = emote.file_path.split('.')[-1] if emote.file_path else 'png'
        cached_file_path = f"cache/{source_hash[:2]}/{cache_key}.{file_ext}"
        
        print(f"  📁 Cache file path: {cached_file_path}")
        print(f"  📦 File extension: {file_ext}")
        print(f"  📊 Result data size: {len(result_image_data)} bytes")

        # Upload to S3
        with tempfile.NamedTemporaryFile(suffix=f'.{file_ext}', delete=False) as temp_file:
            temp_file.write(result_image_data)
            temp_file.flush()
            print(f"  💾 Temp file created: {temp_file.name}")

            try:
                print(f"  🌐 Uploading to S3...")
                db.s3_client.upload_file(
                    temp_file.name,
                    'emote',
                    cached_file_path,
                    ExtraArgs={'ACL': 'public-read', 'ContentType': f'image/{file_ext}'}
                )
                print(f"  ✅ S3 upload successful")

                # Store cache entry in database
                print(f"  🗂️ Storing cache entry in database...")
                success = await db.store_cached_effect(
                    cache_key=cache_key,
                    source_emote_name=emote.name,
                    source_guild_id=emote.guild_id,
                    source_image_hash=source_hash,
                    effect_combination=effect_combination,
                    cached_file_path=cached_file_path,
                    file_size=len(result_image_data)
                )
                
                if success:
                    print(f"  ✅ Database storage successful")
                    print(f"  🎉 Cache storage complete - key: {cache_key}")
                else:
                    print(f"  ❌ Database storage failed")

                return success

            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_file.name)
                except:
                    pass

        return False
    except Exception as e:
        print(f"Cache storage error: {e}")
        return False


async def create_pipeline(cog_instance, message, emote: Emote, queued_effects: list):
    """
    Constructs a processing pipeline for an emote based on queued effects.
    Validates effects, checks permissions, and handles conflicts.
    Includes cache checking to avoid reprocessing identical effect combinations.

    Args:
        cog_instance: The cog instance (for permissions).
        message: The discord message or interaction.
        emote (Emote): The initial emote object.
        queued_effects (list): List of (effect_name, effect_args) tuples.

    Returns:
        list: A list of awaitable functions representing the pipeline steps.
    """
    from ..slash_commands import SlashCommands  # Local import

    # Check cache first if we have effects to apply
    if queued_effects:
        cache_result = await check_effects_cache(cog_instance, emote, queued_effects)
        if cache_result:
            # Return cached result immediately
            emote.img_data = cache_result
            # Filter out non-visual effects for clearer cache messaging
            visual_effects = filter_visual_effects(queued_effects)
            visual_effect_names = [effect[0] for effect in visual_effects]
            emote.notes["cache_retrieved"] = f"Effects loaded from cache for visual effects: {visual_effect_names}"
            emote.notes["cache_hit"] = "Effects loaded from cache"  # Keep for internal tracking
            print(f"Cache hit - effects loaded from cache for visual effects: {visual_effect_names}")
            return [(lambda _: emote)]  # Return emote with cached data

    pipeline = [(lambda _: initialize(emote))]
    effects_list = SlashCommands.EFFECTS_LIST
    permission_list = SlashCommands.PERMISSION_LIST
    seen_effects = set()

    for effect_name, effect_args in queued_effects:
        effect_info = effects_list.get(effect_name)

        # --- Validation ---
        if effect_info is None:
            emote.issues[f"{effect_name}_lookup"] = "EffectNotFound"
            continue

        if effect_info.get("single_use", False):
            if effect_name in seen_effects:
                emote.issues[f"{effect_name}_usage"] = "DuplicateNotAllowed"
                continue
            seen_effects.add(effect_name)

        # --- Permissions ---
        perm_key = effect_info.get("perm", "everyone")
        perm_func = permission_list.get(perm_key)
        allowed = False
        if perm_func:
            # Handle owner check specifically if needed by the permission function implementation
            if perm_key == "owner":
                # Assuming cog_instance.bot exists and has is_owner
                allowed = await cog_instance.bot.is_owner(message.author)
            else:
                allowed = perm_func(message, cog_instance)
        else:
            # Log if a permission key is defined but not found in the list
            print(f"Warning: Unknown permission key '{perm_key}' for effect '{effect_name}'")
            allowed = False  # Default to not allowed if key is invalid

        if not allowed:
            emote.issues[f"{effect_name}_permission"] = "PermissionDenied"
            continue

        # --- Conflicts ---
        applied_conflicts = []
        for group in CONFLICT_GROUPS:
            if effect_name in group:
                # Check if any other effect from the same group is already added
                conflicts_in_group = group.intersection(emote.effect_chain.keys())
                conflicts_in_group.discard(effect_name)  # Don't conflict with self
                if conflicts_in_group:
                    applied_conflicts.extend(list(conflicts_in_group))

        if applied_conflicts:
            conflicts_str = ', '.join(applied_conflicts)
            emote.errors[effect_name] = f"Conflict with: {conflicts_str}"
            emote.issues[f"{effect_name}_conflict"] = f"Conflicts with {conflicts_str}"
            continue

        emote.effect_chain[effect_name] = True  # Mark effect as added

        # --- Pipeline Step Creation ---
        is_blocking = effect_info.get("blocking", False)
        func = effect_info['func']
        args_tuple = tuple(effect_args)
        # Capture name for error reporting inside the wrapper
        _effect_name_captured = effect_name

        if is_blocking:
            # Wrapper for sync effects needing executor
            async def blocking_wrapper(current_emote: Optional[Emote], _func=func, _args=args_tuple,
                                       _name=_effect_name_captured):
                if not current_emote: return None  # Skip if previous step failed critically
                if current_emote.img_data is None and _name != 'initialize':
                    current_emote.errors[_name] = "Skipped: No image data"
                    return current_emote
                try:
                    loop = asyncio.get_running_loop()
                    # Execute synchronous function in a thread pool
                    modified_emote = await loop.run_in_executor(None, _func, current_emote, *_args)
                    return modified_emote
                except Exception as e:
                    tb = traceback.format_exc()
                    if current_emote:
                        current_emote.errors[f"{_name}_executor"] = f"Execution Error: {e}\n```\n{tb}\n```"
                    print(f"Error in executor for '{_name}': {e}")
                    return current_emote  # Return state with error recorded

            pipeline.append(blocking_wrapper)

        else:
            # Wrapper for async effects or non-blocking sync effects
            async def non_blocking_wrapper(current_emote: Optional[Emote], _func=func, _args=args_tuple,
                                           _name=_effect_name_captured):
                if not current_emote: return None
                if current_emote.img_data is None and _name != 'initialize':
                    current_emote.errors[_name] = "Skipped: No image data"
                    return current_emote
                try:
                    # Await if func is async, call directly if sync
                    if inspect.iscoroutinefunction(_func):
                        modified_emote = await _func(current_emote, *_args)
                    else:
                        modified_emote = _func(current_emote, *_args)
                    return modified_emote
                except TypeError as e:
                    tb = traceback.format_exc()
                    if current_emote:
                        err_key = f"{_name}_args"
                        if "positional arguments" in str(e) or "required positional argument" in str(e):
                            current_emote.errors[err_key] = f"Incorrect arguments.\n```\n{tb}\n```"
                        else:
                            current_emote.errors[err_key] = f"Invalid arguments: {e}\n```\n{tb}\n```"
                    print(f"Argument error in '{_name}': {e}")
                    return current_emote
                except Exception as e:
                    tb = traceback.format_exc()
                    if current_emote:
                        current_emote.errors[f"{_name}_execution"] = f"Execution Error: {e}\n```\n{tb}\n```"
                    print(f"Error in effect '{_name}': {e}")
                    return current_emote

            pipeline.append(non_blocking_wrapper)

    return pipeline


async def execute_pipeline(pipeline: list, cog_instance=None, queued_effects: list = None) -> Optional[Emote]:
    """
    Executes the pipeline steps sequentially and caches successful results.

    Args:
        pipeline (list): The list of awaitable functions (steps).
        cog_instance: The cog instance (for cache operations).
        queued_effects (list): List of (effect_name, effect_args) tuples for caching.

    Returns:
        Optional[Emote]: The final Emote state, or None on critical failure.
    """
    emote_state: Optional[Emote] = None
    current_step_name = "initialize"  # Start with initialize step

    for operation in pipeline:
        start_time = time.monotonic()
        # Try to get a better name for logging/errors if it's a wrapper
        op_name = getattr(operation, '__name__', 'unknown_step')
        if op_name in ('blocking_wrapper', 'non_blocking_wrapper') and hasattr(operation,
                                                                               '__closure__') and operation.__closure__:
            try:
                closure_vars = inspect.getclosurevars(operation)
                if '_name' in closure_vars.nonlocals:
                    op_name = closure_vars.nonlocals['_name']
            except Exception:
                pass  # Ignore errors getting closure info

        current_step_name = op_name  # Update step name for error reporting

        try:
            # Execute step with timeout
            emote_state = await asyncio.wait_for(operation(emote_state), timeout=60.0)

            if emote_state is None:
                print(f"Critical Error: Pipeline step '{current_step_name}' returned None.")
                return None  # Abort pipeline

            # Check if the step itself recorded a critical error
            critical_error = False
            if hasattr(emote_state, 'errors') and isinstance(emote_state.errors, dict):
                # Check for specific error keys indicating pipeline should stop
                for key in emote_state.errors.keys():
                    if key == "timeout" or key == "pipeline_execution" \
                            or key.endswith("_executor") or key.endswith("_execution"):
                        critical_error = True
                        break

            if critical_error:
                print(f"Pipeline halted after step '{current_step_name}' due to error recorded within step.")
                break  # Stop processing further steps

            # elapsed = time.monotonic() - start_time # Optional: log time per step

        except asyncio.TimeoutError:
            error_msg = f"Pipeline step '{current_step_name}' timed out (60s)."
            print(error_msg)
            if emote_state and hasattr(emote_state, 'errors'):
                emote_state.errors["timeout"] = error_msg
            else:  # Timeout likely happened early, before emote_state was initialized properly
                return None  # Cannot reliably add error, return None
            break  # Stop pipeline on timeout

        except Exception as e:
            tb = traceback.format_exc()
            error_msg = f"Pipeline Error during '{current_step_name}': {e}\n```\n{tb}\n```"
            print(error_msg)
            if emote_state and hasattr(emote_state, 'errors'):
                emote_state.errors["pipeline_execution"] = error_msg
            else:  # Error happened early
                return None
            break  # Stop pipeline on general error

    # Store successful results in cache (if we have the required parameters)
    if (emote_state and cog_instance and queued_effects and
            emote_state.img_data and not emote_state.errors and
            "cache_hit" not in emote_state.notes):

        # Check if there are any validation issues (misspelled effects, etc.)
        has_validation_issues = bool(emote_state.issues) if hasattr(emote_state, 'issues') else False

        # Skip caching if we have validation issues
        if has_validation_issues:
            issue_keys = list(emote_state.issues.keys())
            emote_state.notes["cache_skipped"] = f"Caching skipped due to validation issues: {', '.join(issue_keys)}"
            print(f"Caching skipped due to validation issues: {issue_keys}")

        else:
            # Filter out non-visual effects for caching
            visual_effects = filter_visual_effects(queued_effects)

            # Only cache if there are visual effects
            if visual_effects:
                try:
                    # Store in cache using only visual effects
                    cache_success = await store_effects_cache(cog_instance, emote_state, visual_effects,
                                                              emote_state.img_data)
                    if cache_success:
                        visual_effect_names = [effect[0] for effect in visual_effects]
                        emote_state.notes[
                            "cache_stored"] = f"Result processed and cached for visual effects: {visual_effect_names}"
                        print(f"Result cached successfully for visual effects: {visual_effect_names}")
                    else:
                        emote_state.notes["cache_failed"] = "Result processed but caching failed"
                except Exception as e:
                    print(f"Failed to cache result: {e}")
                    emote_state.notes["cache_error"] = f"Result processed but caching error: {str(e)}"
                    # Don't fail the whole operation if caching fails
            else:
                # Only non-visual effects were present
                non_visual_names = [effect[0] for effect in queued_effects]
                emote_state.notes["cache_skipped"] = f"Caching skipped - only non-visual effects: {non_visual_names}"
                print(f"Caching skipped - only non-visual effects: {non_visual_names}")

    return emote_state
