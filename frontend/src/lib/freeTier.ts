/**
 * The sentence that goes beside every mention of a free cloud tier.
 *
 * A free tier is paid for in prompts, and Zaram says so. What it had
 * stopped saying in the same breath — asked for 14 September 2026 — is the
 * other half of the deal: the model on this machine is *also* free, costs
 * nothing per question, and nothing said to it leaves or is trained on.
 * Without that, "free tier · prompts are logged" reads as the only free
 * option and its price; with it, the choice is between two free things
 * and what each one costs.
 *
 * One constant, so it is the same sentence in first run, Settings, the
 * routing picker and the offer under a reply. It is only ever *added* to
 * the provider's own disclosure, never used in place of it.
 */
export const LOCAL_IS_FREE =
  'Local is free too: a model on this machine costs nothing per question, and nothing you say to it leaves this device or is trained on.';
