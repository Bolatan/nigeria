Polling unit data: https://github.com/mykeels/inec-polling-units (MIT, see LICENSE-polling-units.txt).
Derived from INEC's polling unit list (snapshot from 2022: 176,623 units, 119,297 with coordinates).
Coordinates were geocoded from unit names; many are approximate (area-level) and some were wrong (removed on load).

Constitution text (data/constitution.md): https://github.com/mykeels/nigerian-constitution (last updated Feb 2018; repo has no license file).
KNOWN LIMITS: pre-2018 text. It lacks the Fourth (2017/2018) and Fifth (2023) Alterations, e.g. Section 131 still says
the President must be 40 (now 35). Section 168 is missing, and the Schedules are not included.
For the current text, download the 2023 PDF (constituteproject.org or FAOLEX) and run: python ingest.py <file.pdf>
