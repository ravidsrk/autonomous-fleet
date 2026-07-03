# doc-sync audit — DRIFT INDEX (frozen)

Run: 20260703T054520Z-doc-sync-3e8173 · Target: ravidsrk/gemoji @ master (synced to github/gemoji upstream)
Auditor: codex exec (sandboxed, fresh session). README API examples verified by execution
(`ruby -Ilib -rgemoji`, `script/console </dev/null`). `script/test` behaviour VERIFY-MANUALLY
(local bundle gems missing at audit time).

## README

No discrepancies found (API examples execute as documented).

## DRIFT INDEX

| ID | Doc file:line | Doc says | Code truth | Fix area | State |
|----|---------------|----------|------------|----------|-------|
| D-001 | `CONTRIBUTING.md:11` | Ruby prerequisite is "Ruby 1.9+" | CI verifies only Ruby 2.7/3.0/3.1 (`.github/workflows/test.yml:10`); Bundler 2.4.10 in `Gemfile.lock:24-25` | contributing | CLOSED via PR#8 |
| D-002 | `CONTRIBUTING.md:30` | `script/release` "commits the change" | Commits BOTH `gemoji.gemspec` and `Gemfile.lock` (`script/release:28`), after tests/build (`script/release:23,27`) | contributing | CLOSED via PR#8 |
| D-003 | `CONTRIBUTING.md:31` | Release pushes to GitHub and RubyGems.org | Pushes `HEAD` + tag to `origin` (`script/release:30`) then gem push (`script/release:31`); no GitHub-specific validation | contributing | CLOSED via PR#8 |
| D-004 | `script/release:5` | Step 2 "commits gemspec" | Commit includes `gemoji.gemspec Gemfile.lock` (`script/release:28`) | comments | CLOSED via PR#9 |
| D-005 | `lib/emoji.rb:29` | `edit_emoji` updates indices when aliases/unicode aliases changed | Only writes CURRENT aliases/unicodes into indexes (`lib/emoji.rb:37-42`); stale entries not removed (verified by deleting an alias in an edit block) | comments | CLOSED via PR#9 |
| D-006 | `lib/emoji/character.rb:22` | Category comes from Apple's character palette | Categories come from Unicode `# group:` data (`db/emoji-test-parser.rb:31-34`, `db/dump.rb:28`, `lib/emoji.rb:118`) | comments | CLOSED via PR#9 |
| D-007 | `Rakefile:11` | `db:generate` "generates Emoji data files" | Task only ensures/downloads `vendor/unicode-emoji-test.txt` (`Rakefile:12-13,22-23`); `db:dump` prints JSON (`Rakefile:16-18`) | comments | CLOSED via PR#9 |
