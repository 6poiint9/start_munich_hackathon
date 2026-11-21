"""Tunable assumptions. Every value here is a guess until Soony confirms it.

The values are not copied from the data. They are starting points that the
team must replace with answers from the office hours. Each value names the
person who can confirm it.
"""

TIMEZONE = "Europe/Berlin"

# Hours without a status update before a shipment counts as "silent".
# Confirm with Felix Brunner or Raj Patel (logistics).
SILENT_AFTER_HOURS = {"sea": 24.0, "air": 12.0, "road": 8.0}

# Days for the last leg when a shipment ends at a port or airport and the
# master data has no route for the last leg.
DEFAULT_LAST_LEG_DAYS = 1.0

# Days to collect a container that waits at the port.
PORT_PICKUP_DAYS = 1.0

# Which edition gets shared parts first. Source: launch_status.xlsx note
# "Priority per CPO memo of today: Collector's pre-orders first."
# Confirm with Dr. Maren Vogt.
EDITION_PRIORITY = ("FG-GH6-CE", "FG-GH6-STD")

# Cost of one missing copy on day one, in EUR. Unknown. Ask Dr. Maren Vogt.
COST_PER_MISSING_COPY_EUR: dict[str, float | None] = {
    "FG-GH6-STD": None,
    "FG-GH6-CE": None,
}

# Hours between arrival at Hamburg and the first part on the pack line
# (unloading, receiving, inspection). Confirm with Felix Brunner.
RECEIVING_HOURS = 4.0

# Products that are part of this launch.
LAUNCH_PRODUCTS = ("FG-GH6-STD", "FG-GH6-CE")
