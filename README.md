# tuckaway

a terminal app to quickly back up critical directories and files on your system into a single encrypted zip.

## what it does

- copies one or more source directories into a single snapshot
- compresses everything into an aes-encrypted `.zip` (password set at runtime, never stored)
- skips files and folders you don't want with shell-style ignore patterns (`*.log`, `node_modules`, `.git`, etc.)

from the menu:

- add your source directories (`1`)
- set a backup destination (`3`)
- optionally set ignore patterns (`5`) and compression level (`4`)
- start backup (`6`), enter a password
  
output is a timestamped encrypted zip in your destination folder.

## notes

- every run is a full archive, not incremental
- ignore patterns are shell wildcards, not regex or gitignore syntax
- config lives in your platform user data dir as `config.json`

## requirements

python 3.13+. depends on `pyzipper`, `questionary`, `rich`, `platformdirs`.
