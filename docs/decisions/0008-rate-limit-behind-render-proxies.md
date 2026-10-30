# 0008: Count trusted proxy hops from the right

Date: 30 October 2026
Status: accepted

## Context

The rate limiter first keyed on the connection's own address. On Render every visitor arrives through Render's proxy, so all visitors would share one counter. Trusting the left-most `X-Forwarded-For` entry is no fix, because a visitor can write that part of the header themselves.

## Decision

Add `WEEDLAB_TRUSTED_PROXY_HOPS`. The API reads that many entries from the right of `X-Forwarded-For`, because each trusted proxy appends the address it saw and anything a visitor invents ends up on the left. The default is 0, which ignores the header, so local runs behave as before. If the header is missing or too short, the connection's own address is used.

The right number was found by logging the header on Render. It looks like this: real visitor, a Cloudflare address, Render's internal address. So the value on Render is 3. Values of 1 and 2 read a Cloudflare address that changes between requests, and 12 quick requests were all let through. With 3, the 11th and 12th request got a 429, and a phone on mobile data could still run a detection while the PC was blocked.

## Consequences

- The number depends on Render's proxy layout. If Render changes it, check again by sending 12 bad uploads quickly and expecting a 429 on the 11th.
- The limiter lives in memory, so it resets on restart and is not shared between workers.
- A temporary debug log line that printed visitors' addresses was merged to find the header shape, then reverted and redeployed.