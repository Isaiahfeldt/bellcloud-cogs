from .base import Emote


async def train(emote: Emote, amount: int = 3) -> Emote:
    """
        Duplicate the provided Emote for a specified number of times within a valid range.

        User:
            Creates multiple copies of the emote in a row. You can specify a
            number between 1-6 to control how many copies appear.

            Default is 3 if no number is provided.
            This effect can only be used once per emote.

            Usage:
            `:aspire_train:` - Creates 3 copies of the emote.
            `:aspire_train(5):` - Creates 5 copies of the emote.


        Parameters:
            emote (Emote): The emote object to be trained.
            amount (int): The number of times to train the emote. If invalid, defaults
                to 3. Must be an integer between 1 and 6, inclusive.

        Returns:
            Emote: The updated emote object with the training details and potential
                error messages.
    """
    from emote.slash_commands import SlashCommands

    try:
        amount = int(amount)
    except (ValueError, TypeError):
        amount = 3
        emote.errors["train"] = "Train amount must be a number."
    else:
        if not 1 <= amount <= 6:
            amount = min(max(amount, 1), 6)
            emote.errors["train"] = "Train amount must be between values of 1 and 6."
            emote.followup["Train"] = (
                "This effect is capped at 6 to avoid Discord rate limits and to"
                "prevent spamming, which can lead to Bell being blacklisted. Sorry!"
            )

    SlashCommands.train_count = amount
    return emote
