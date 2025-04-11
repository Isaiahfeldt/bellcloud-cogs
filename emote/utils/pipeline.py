# File: emote/utils/pipeline.py (Refactored)

import asyncio
import inspect
import time
import traceback
from typing import Optional

from .effects import Emote, initialize

# Define groups of effects that cannot be used together
CONFLICT_GROUPS = [
    # Example: {"speed", "fast", "slow"},
]


async def create_pipeline(cog_instance, message, emote: Emote, queued_effects: list):
    """
    Constructs a processing pipeline for an emote based on queued effects.
    Validates effects, checks permissions, and handles conflicts.

    Args:
        cog_instance: The cog instance (for permissions).
        message: The discord message or interaction.
        emote (Emote): The initial emote object.
        queued_effects (list): List of (effect_name, effect_args) tuples.

    Returns:
        list: A list of awaitable functions representing the pipeline steps.
    """
    from ..slash_commands import SlashCommands  # Local import

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
                # try:
                # Await if func is async, call directly if sync
                if inspect.iscoroutinefunction(_func):
                    modified_emote = await _func(current_emote, *_args)
                else:
                    modified_emote = _func(current_emote, *_args)
                return modified_emote
                # except TypeError as e:
                #     tb = traceback.format_exc()
                #     if current_emote:
                #         err_key = f"{_name}_args"
                #         if "positional arguments" in str(e) or "required positional argument" in str(e):
                #             current_emote.errors[err_key] = f"Incorrect arguments.\n```\n{tb}\n```"
                #         else:
                #             current_emote.errors[err_key] = f"Invalid arguments: {e}\n```\n{tb}\n```"
                #     print(f"Argument error in '{_name}': {e}")
                #     return current_emote
                # except Exception as e:
                #     tb = traceback.format_exc()
                #     if current_emote:
                #         current_emote.errors[f"{_name}_execution"] = f"Execution Error: {e}\n```\n{tb}\n```"
                #     print(f"Error in effect '{_name}': {e}")
                #     return current_emote

            pipeline.append(non_blocking_wrapper)

    return pipeline


async def execute_pipeline(pipeline: list) -> Optional[Emote]:
    """
    Executes the pipeline steps sequentially.

    Args:
        pipeline (list): The list of awaitable functions (steps).

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

    return emote_state
