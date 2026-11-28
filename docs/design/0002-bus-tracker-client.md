# 0002: Bus Tracker client

## Context

The service polls CTA's Bus Tracker API for vehicle positions and CTA's own arrival predictions. The client's one job is to take a request that is ready to send and return typed data reliably. It doesn't decide what to poll, when, or how often: the poller ([#4](https://github.com/joshuahaddad/chicago-streets/issues/4)) owns the schedule and the request budget, and storage.

Two kinds of data are in play. GTFS ([#5](https://github.com/joshuahaddad/chicago-streets/issues/5)) is the plan: routes, trips, stops and stop times, versioned by feed date. Bus Tracker is the actuals: where buses are now. When the two disagree, live data is the actuals and stored data is only the plan.

The API's limits and terms are noted on [#3](https://github.com/joshuahaddad/chicago-streets/issues/3): 100,000 calls a day per key, with no stated burst limit.

## Decisions

**No general HTTP client of our own.** `httpx` builds URLs from a base URL, path and parameters, and sends requests. `tenacity` retries a call on a condition we pass it, with backoff. A client class of ours would only repeat them. Both are new dependencies.

**`CTABusAPI` holds everything specific to Bus Tracker.** It knows the endpoints, their arguments, and the frozen dataclasses each one returns. It takes an `httpx.Client` as an argument, so tests pass one backed by `httpx.MockTransport` and recorded responses.

**`CTABusAPI` classifies each response.** Bus Tracker reports most errors inside an HTTP 200, so the status code alone can't say whether a call failed. `CTABusAPI` reads the body, decides whether it is an error and whether that error is worth retrying, and hands that decision to `tenacity`. A call for several routes can return data for some and an error for others. Only the routes with a retryable error are retried, and `CTABusAPI` merges the retried results into the first ones.

**Error handling:**

| What came back | What the client does |
|---|---|
| A timeout, or HTTP 5xx | Retry with exponential backoff and a few attempts, then raise |
| Daily limit exceeded | Raise at once, with its own exception |
| Invalid API key | Raise at once, with its own exception |
| `No data found` for a route | An empty result for that route, not an error: at 2am a route can have no buses |
| A record that is malformed (for example, missing `lat`, or a `tmstmp` in a format we don't expect) | Retry within the same limits. Then keep the valid records and drop the malformed ones. Malformed data is never stored |

The exceptions share the package's one base class.

**Retries end before the next poll.** The worst case is every attempt timing out: N·T plus the sum of the waits between attempts, for N attempts with timeout T. That total must stay under the poll interval, or two polls for the same data overlap. The numbers are configuration. A default that fits a 30-second poll is T = 5 s with 3 attempts and waits of 1 s and 2 s, which comes to 18 s.

**The raw response is kept as well as the parsed data.** If the response format changes, every record could be dropped as malformed, and the poller would store nothing, just as at 2am when no buses run. Keeping the raw body is what lets us tell "CTA sent 300 and we dropped 300" from "CTA sent nothing", and lets us reparse later. The client returns the raw body alongside the parsed records, and #4 stores it.

**No response cache in the client.** The poller always wants positions newer than the last ones, so a cached position is never the right answer.

**Patterns are fetched by `pid`.** Each vehicle carries a `pid` (a pattern: one specific path, including detours) and a `pdist` (distance along it, in feet). GTFS doesn't have Bus Tracker's patterns, so `pdist` means nothing without `getpatterns`. The client provides `get_patterns(pids)`. An unseen `pid` is expected data, not a malformed record: it means a pattern to look up. When to fetch, and how patterns are stored and versioned, belong to #4.

## Alternatives

- **A general client for any API, with the response classifier injected.** It keeps the client free of CTA rules. But merging partial results needs to know the shape of `bustime-response`, so the client would either hold CTA knowledge or return every attempt for the caller to combine. Once the classifier and the merge are CTA-specific, what remains is what `httpx` and `tenacity` already do.
- **An injected cache in the client.** It would only help slow-moving reference data, and that comes from GTFS in Postgres, or for patterns, from #4's store.
- **Treat a `No data found` route as invalid.** At 2am that's the correct answer for a route with no buses. A mistyped route is caught instead by checking the poller's config against a route list (#4).

## Tradeoffs

Retrying a whole call because one record is malformed spends requests from the budget, and may get the same record back if CTA's own data is wrong. The attempts are capped, so the cost is bounded. Keeping raw responses costs storage in #4.

## Open questions

To confirm in the [v3 developer guide](https://www.transitchicago.com/assets/1/6/cta_Bus_Tracker_API_Developer_Guide_and_Documentation_2025-04-21.pdf) or against recorded responses:

- The base URL, how many routes one `getvehicles` call takes, and the exact error messages.
- Whether errors, including the daily limit, come back inside an HTTP 200, and whether a multi-route call can mix data and errors.
- Whether a nonexistent route returns the same `No data found` message as a route with no buses.
- Whether failed calls count against the daily limit.
- Whether a `pid` ever changes its path over time. Until the guide or our own history says otherwise, assume it can.
- Whether Bus Tracker stop IDs match GTFS `stop_id`s.

For #4:

- The request budget: routes per call × poll interval against 100,000 a day, with retries counted.
- Skipping routes that keep returning `No data found`, and validating the configured routes against GTFS or `getroutes` at start-up.
- Versioned patterns keyed by (`pid`, `updated_at`), and the as-of join from a position to its pattern. `updated_at` is when we noticed a change, not when CTA made it, so positions observed in between join to the old path.

To settle in the build:

- The return type of `get_vehicles`: the parsed records, the raw body, and a count of dropped records, or some other shape.
