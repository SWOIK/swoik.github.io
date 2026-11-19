#!/usr/bin/env python3
"""Unit-economics model for an AI chat-report product (Thai market).

ALL PRICES AND RATES BELOW ARE ILLUSTRATIVE ASSUMPTIONS, not quotes.
Check current LLM provider pricing, FX rate and payment fees before using
these numbers for decisions. Edit the ASSUMPTIONS block and re-run:

    python3 cost_model.py
"""

# ---------------- ASSUMPTIONS (edit me) ----------------
FX_THB_PER_USD = 35.0          # assumed
TOK_PER_MSG = 22               # Thai text + sender + timestamp, compacted (assumed)
CHEAP = dict(inp=0.25, out=1.25)   # USD per 1M tokens, small/fast model (assumed)
STRONG = dict(inp=3.00, out=15.00)  # USD per 1M tokens, writer model (assumed)
CHUNK_TOK = 30_000             # tokens per map chunk
DIGEST_OUT = 2_500             # output tokens per chunk digest
WRITER_FIXED_IN = 9_000        # persona/system prompt + stats + quotes
REPORT_OUT = 7_000             # full report output tokens (Thai is token-heavy)
PREVIEW_SHARE = 0.25           # share of report shown free
SINGLE_PASS_LIMIT = 120_000    # below this the writer reads the whole chat
RETRY = 1.15                   # retries / validation re-runs
SAFETY_FIXED_USD = 0.004       # moderation / safety pass
PAY_FEE_PCT = 0.035            # blended card + PromptPay (assumed)
VAT = 0.07                     # price includes VAT; assume VAT-registered
SCENARIOS = {"S": 1_500, "M": 6_000, "L": 20_000, "XL(cap 25k)": 25_000}
PRICES_THB = {"S": 59, "M": 99, "L": 149, "XL(cap 25k)": 149}
# -------------------------------------------------------

def cost(prices, tin, tout):
    return (tin * prices["inp"] + tout * prices["out"]) / 1e6

def pipeline(msgs, price_mult=1.0):
    tok = msgs * TOK_PER_MSG
    c = SAFETY_FIXED_USD
    if tok <= SINGLE_PASS_LIMIT:
        # one strong pass: reads whole chat
        pre = cost(STRONG, tok + WRITER_FIXED_IN, REPORT_OUT * PREVIEW_SHARE)
        post = cost(STRONG, 0, REPORT_OUT * (1 - PREVIEW_SHARE)) \
            + cost(STRONG, (tok + WRITER_FIXED_IN) * 0.1, 0)  # cached re-read ~10%
        naive_full = cost(STRONG, tok + WRITER_FIXED_IN, REPORT_OUT)
    else:
        chunks = -(-tok // CHUNK_TOK)
        map_c = cost(CHEAP, tok + chunks * 1_500, chunks * DIGEST_OUT)
        writer_in = WRITER_FIXED_IN + chunks * DIGEST_OUT
        pre = map_c + cost(STRONG, writer_in, REPORT_OUT * PREVIEW_SHARE)
        post = cost(STRONG, writer_in * 0.1, REPORT_OUT * (1 - PREVIEW_SHARE))
        naive_full = map_c + cost(STRONG, writer_in, REPORT_OUT)
    return tuple(x * RETRY * price_mult + (c if i == 0 else 0)
                 for i, x in enumerate((pre, post, naive_full)))

def net_thb(price):
    return price / (1 + VAT) * (1 - PAY_FEE_PCT)

def run(price_mult):
    print(f"\n=== LLM price multiplier x{price_mult} | FX {FX_THB_PER_USD} THB/USD ===")
    hdr = ("scn", "msgs", "tokens", "pre-pay฿", "post-pay฿", "full-first฿",
           "price฿", "net฿", "margin(staged)", "breakeven conv (staged)",
           "breakeven conv (full-first)")
    print(" | ".join(hdr))
    for name, msgs in SCENARIOS.items():
        pre, post, naive = pipeline(msgs, price_mult)
        pre_t, post_t, naive_t = (x * FX_THB_PER_USD for x in (pre, post, naive))
        p = PRICES_THB[name]
        n = net_thb(p)
        # staged: every upload costs pre; payer additionally costs post
        # contribution per payer = n - post ; need conv * (n - post) >= pre
        be_staged = pre_t / (n - post_t) if n > post_t else float("inf")
        be_full = naive_t / n if n > 0 else float("inf")
        margin = (n - pre_t - post_t) / n
        print(f"{name} | {msgs:,} | {msgs*TOK_PER_MSG:,} | {pre_t:.1f} | {post_t:.1f} | "
              f"{naive_t:.1f} | {p} | {n:.1f} | {margin:.0%} | {be_staged:.1%} | {be_full:.1%}")

if __name__ == "__main__":
    for m in (0.5, 1.0, 2.0):
        run(m)
    print("\nRead: 'breakeven conv' = share of uploaders who must pay so that the\n"
          "marginal LLM cost of ALL uploads (payers + non-payers) is covered by payers.\n"
          "Excludes infra, ads, support, refunds, free-tier abuse.")
