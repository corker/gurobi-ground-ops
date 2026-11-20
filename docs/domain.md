# Domain: airport ground operations

The words the code and docs use, and how this repo's synthetic version simplifies the real thing.

## Glossary

| Term | Meaning here |
| --- | --- |
| **Turnaround** | The time an aircraft spends on the ground between arriving and departing. Each turnaround creates two tasks: unloading baggage after arrival and loading baggage before departure. |
| **Task** | One piece of work with a fixed start and end time, in minutes after midnight. It needs exactly one handler. |
| **Handler** | A member of the ground staff. A handler does at most one task at a time. |
| **Gap** | The minimum time between two tasks of the same handler, to move between aircraft: a fixed 10 minutes. Two tasks *conflict* if they're closer than that. |
| **Shift window** | The hours a handler is rostered for, such as 06:00 to 12:00. |
| **Overtime** | Minutes of a task that fall outside the handler's shift window. Model 1 minimises total overtime. |
| **Shift pattern** | (Model 2) A start time and length that people can be rostered on, such as 06:00 for 8 hours with one break. |
| **Demand slot** | (Model 2) A half hour of the day with a required number of people on duty. |

## Where the numbers come from

Task durations and ground times follow the [airport ground handling dataset](https://github.com/spadrona/airport_ground_handling_dataset) (file `FE.csv`, 65 turnarounds), sampled from a triangular distribution that runs from the dataset's minimum to its maximum, with the dataset's median as its most likely value:

| Quantity | Minimum | Median | Maximum (minutes) |
| --- | --- | --- | --- |
| Unloading baggage | 7 | 10 | 24 |
| Loading baggage | 8 | 13 | 20 |
| Ground time (arrival to departure) | 26 | 28 | 52 |

Arrivals fall between 06:00 and 14:00. Shift windows start between 05:00 and 10:00 on the half hour and last 4, 6 or 8 hours.

## What's simplified

- **No precedence or skills.** Any handler can do any task, and unloading needn't finish before loading starts.
- **One fixed gap.** Real travel time depends on the distance between stands; here it's always 10 minutes.
- **No breaks, no equipment, no labour rules,** and no team tasks that need several people at once.
- **No uncertainty.** Times are known exactly in advance; there are no delays.
- **Synthetic data only.** IDs are numbers; there are no real airports, airlines or names.

The models stay textbook on purpose; [related-work.md](related-work.md) lists papers that handle the richer versions.
