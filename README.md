# Living Spaces

An open canvas for your bots in Hermes Desktop. Ask in chat and your bot builds dashboards, trackers, mini-apps and visual pieces in a Spaces tab. Each Space keeps its data, and you change it by asking.

## Requirements

- Hermes 0.23.1 or later
- Hermes Desktop
- Qualified on macOS

## Install

Run these commands in the Hermes profile where you want Living Spaces. This installs the reviewed plugin revision from its subdirectory, then enables it:

```sh
hermes plugins install akinduroifedayo/living-spaces/src/living-spaces --ref 8134be424b5a5756a89278e729ab537475f45155 --no-deps --no-enable
hermes plugins enable living-spaces
```

In Desktop, enable **Living Spaces** under **Capabilities > Plugins**, then open **Spaces**. The CLI and Desktop switches enable different parts of the plugin; use both.

### Manual install

You can also clone the repository and copy the plugin into an empty destination in your selected profile. Set `HERMES_HOME` first if you use a non-default profile.

```sh
git clone https://github.com/akinduroifedayo/living-spaces.git
cd living-spaces
git checkout --detach 8134be424b5a5756a89278e729ab537475f45155
plugin_home="${HERMES_HOME:-$HOME/.hermes}"
mkdir -p "$plugin_home/plugins"
test ! -e "$plugin_home/plugins/living-spaces" && \
  cp -R src/living-spaces "$plugin_home/plugins/living-spaces"
hermes plugins enable living-spaces
```

Then enable the Desktop switch described above. The plugin lives in `src/living-spaces`; the repository root is not the plugin package.

The [package README](src/living-spaces/README.md) explains usage, saved data, upkeep, and removal.

## Repository documentation

The [specification](docs/spec/SPEC.md) and [amendments](docs/spec/AMENDMENTS.md) record scope. The [evidence ledger](docs/evidence/R1-STATUS.md) contains historical qualification receipts. Saved chat traces and selected probe dumps are omitted from the current tree; earlier commits retain that history.

## License

Living Spaces is licensed under the [MIT License](LICENSE), copyright Living Spaces contributors. Vendored libraries and fonts retain their own licenses. See the [third-party notices](src/living-spaces/THIRD-PARTY.md).
