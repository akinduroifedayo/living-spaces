## Build from a complete example

Read all files in [Research Desk](research-desk/index.html) before
using this example. Copy their contents into the create tool's `files` object
under these paths. Do not send filesystem paths as file contents.

- [space.json](research-desk/space.json) declares collections and a public feed.
- [index.html](research-desk/index.html) loads CSS and the application module.
- [app.js](research-desk/app.js) provides the shared store and navigation.
- [views/overview.js](research-desk/views/overview.js) shows counts and source/run timestamps.
- [views/library.js](research-desk/views/library.js) implements search, creation, and detail.
- [views/queue.js](research-desk/views/queue.js) edits status, priority, and notes.
- [views/editor.js](research-desk/views/editor.js) preserves drafts and resolves conflicts.
- [styles.css](research-desk/styles.css) defines the layout.

The app starts with an honest empty state. Create a clearly labeled demo record
through its form or `spaces_write_records` if the user wants sample content.
Do not label fixtures as fetched research.

For a different application, read the [habit planner](habit-planner.md).
It stores daily check-ins without a feed or schedule.
Use the same record, revision, and save rules for games and other applications.
