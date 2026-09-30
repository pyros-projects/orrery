# Plan: library completion by any part of the name; galaxy folders, delete, export

Status: approved 2026-09-30. Two independent pieces: a completion fix and three
galaxy features.

## 1. Library completion matches any part of the name

`__hai` offers every library whose full name contains `hai`, case-insensitive,
not only names that start with it. Ranking, alphabetical within each tier:

1. the name starts with the query (`hair_color`)
2. a path or word part starts with it (`characters/gothic/hair`, `looks/face_hair_female`);
   a part starts after `/` or `_`
3. the query appears anywhere else (`chair`)

Only library names change. Tags after `[` and property filters after `#` keep
prefix matching.

## 2. Galaxy folders (virtual)

Folders exist only in the galaxy. Files stay where ComfyUI wrote them.

- A row carries an optional `folder`, a path such as `portraits/demons`. Absent
  or empty means unsorted. Row ids are unchanged (`ts|media|seed`).
- `galaxy_folders.json` in the home keeps the folder list, so empty folders
  survive. The folder list the app sees is that file plus every folder a row
  names, plus their parents.
- A folder path is parts joined by `/`. A part is any text without `/` or
  control characters, trimmed, at most 60 characters, and never `.` or `..`.
  Case is kept.
- Moving outputs sets their `folder`.
- Moving a folder into another folder renames its prefix (`a/b` into `c` gives
  `c/b`); subfolders and rows move along. A folder cannot move into itself or
  its own subfolder, and a move onto an existing name is refused.
- Deleting a folder is not destructive: its outputs and subfolders move up one
  level.

## 3. Deleting outputs

- The rows leave `galaxy.jsonl`.
- Each media file moves to `trash/` in the home (a suffix on a name clash). A
  file that is already gone is fine.
- The row's thumbnail is deleted.
- Learned weights stay as they are: a rating was a real judgement.

## 4. Exporting sidecar pairs

`export/<name>/` in the home receives, for every selected output with a file:

- a copy of the file, under its own name
- `<stem>.txt` next to it, holding the row's `text` (the prompt that made it),
  UTF-8

A name clash inside the export folder gets `_2`, `_3`, … on both files of the
pair. An existing export folder is added to, so a dataset can grow over several
exports. Rows without a file are skipped and counted. Export names are one
folder name (letters, digits, `_`, `-`, `.`, spaces), never a path.

## 5. API

- `GET /orrery/galaxy` takes `folder` (absent: everything; empty: unsorted;
  a path: that folder's own outputs) and filters on the server, so the row
  limit applies per folder. The answer adds `folders: [{path, count}]` counted
  over all rows, and each row carries `folder`.
- `POST /orrery/galaxy/move` `{ids, folder}`
- `POST /orrery/galaxy/delete` `{ids}` → `{deleted}`
- `POST /orrery/galaxy/export` `{ids, name}` → `{path, exported, skipped}`
- `POST /orrery/galaxy/folder/add` `{path}`
- `POST /orrery/galaxy/folder/rename` `{path, to}`
- `POST /orrery/galaxy/folder/delete` `{path}`

Folder routes answer with the new folder list. Unknown ids are 404, bad names
400, clashes 409.

## 6. Galaxy tab

- **Folder tree** on the left, as wide as you drag it (the node remembers the
  width, like the library list): *All outputs*, *Unsorted*, then the nested
  folders with counts and disclosure arrows. `+` makes a subfolder of the
  current folder; double-click renames; a trash icon on hover deletes.
- **Drag and drop.** A card dropped on a folder moves there; if the card is
  selected, the whole selection moves. A folder dropped on a folder nests.
  Dropping on *All outputs* or *Unsorted* moves to the top level. Drops are
  handled inside the app, so ComfyUI never tries to load them as a workflow.
- **Selection.** Every card has a checkbox, shown on hover and always once
  something is selected. Shift-click selects a range, Ctrl/Cmd-click on a card
  selects instead of opening it. A bar shows while anything is selected:
  `N selected · Select all · Clear · Export pairs · Delete`. *Select all* takes
  the visible cards.
- **Delete** asks first, naming the count and the trash folder.
- **Export** asks for a name, prefilled with the current folder's name or
  `selection-YYYY-MM-DD`; a toast names the folder and any skipped outputs.

## 7. Tests

- pytest: move, delete (trash, thumbnail, weights kept), folder list, rename
  into another folder, folder delete, export (sidecar text, clashes, missing
  files, existing folder), the new routes and the `folder` filter.
- node: completion ranking; the folder tree built from the list; range
  selection.
- Browser, on the isolated CPU ComfyUI on :8190 with a scratch home: create
  folders, drag cards and folders, select a range, export (files checked on
  disk), delete (trash checked on disk).

## Out of scope

Rubber-band selection, a "Move to…" menu, undo for moves, a trash view, a
delete button in the detail panel.
