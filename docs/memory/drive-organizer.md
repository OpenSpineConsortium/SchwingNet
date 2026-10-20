The drive organizer sorts a whole drive into proposed projects: catalog, organize (one Claude run), accept, each started by hand in a private repository.

.github/workflows/drive-organize.yml and tools/drive_organize.py read every folder and file
that drive.json's "organize" items hold (the drive's root id "root" for all of it) into
catalog.json, TREE.md and digests.jsonl on the branch drive-catalog, with no Claude. The
organize step has Claude return projects as JSON, opened as epics labelled epic, proposed,
drive and project:<slug>, with tasks labelled proposed, never todo, under "Project: #N" in
place of "Epic: #N", so no worker spends and no integration starts until the owner runs
accept, which labels the epic tracking and adds its folders to drive.json by a pull request;
drive-sync.yml's run then calls `drive_organize.py ready`, which gives the tasks todo and
their workers' labels once the folders are in the repository. Claude's text is cleaned of
comment marks, since the organizer reads its own hidden lines. A slug proposed before is never
proposed again, so closing a proposal says no. tools/file_digest.py reads Word, Excel, CSV,
PowerPoint, notebooks, code, PDFs and images as text for Claude and for workers. A session
(.claude/skills/drive-organize) starts the workflow's Graph walk, proposes projects, some with a
Symphony repository of their own that people join, opens them through the step open, and plans
the moves into "Symphony projects/" (tools/drive_connector.py) for the owner's go, every move
undoable. The walk through the Microsoft 365 connector is retired on the owner's word of
2026-10-20: the drive is read only under the owner's Microsoft sign-in, and moves wait for a
Graph step (docs/research/onedrive-direct-graph.md). The design is docs/research/drive-organizer.md.

Wayne State approved the SymphonyBoard Folders app for its accounts on 2026-10-19, as the owner reported that day, so a WSU OneDrive can be read natively through Microsoft Graph with the panel's sign-in; the connector path stays until each piece switches, and both run one code path (docs/start/capabilities.md).
