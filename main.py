import json
import os
import shutil
from pathlib import Path

import pyzipper
import questionary
from platformdirs import user_data_dir
from questionary import Choice, Separator, select
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress

console = Console()

data_dir = Path(user_data_dir("tuckaway"))
config_path = data_dir / "config.json"

IGNORE_HELP = r"""[bold cyan]IGNORE PATTERNS[/]
  Patterns decide which files and folders get skipped. Each pattern is
  matched against the [italic]name[/] of each item (not its full path),
  using shell-style wildcards:

    [green]*[/]        matches any characters    [dim]->[/]  [green]*.log[/]   skips file.log, error.log
    [green]?[/]        matches one character     [dim]->[/]  [green]tmp?[/]    skips tmp1, tmpA
    [green]\[abc][/]    matches one listed char   [dim]->[/]  [green]v\[12][/]   skips v1, v2
    [green]\[0-9][/]    matches one char in range [dim]->[/]  [green]\[0-9]*[/]  skips anything starting 0-9
    [green]\[!abc][/]   matches one NOT listed    [dim]->[/]  [green]\[!_]*[/]   skips names not starting _

  Matching is on the base name only, so [green]temp[/] matches a 'temp' folder
  anywhere in the tree. When a folder matches, everything inside it is
  skipped too.

  [bold]EXAMPLES[/]
    [green]*.pyc[/]          compiled Python files
    [green]__pycache__[/]    Python cache folders
    [green].git[/]           git repos
    [green]node_modules[/]   dependency folders
    [green]*.log *.tmp[/]    logs and temp files
    [green].DS_Store[/]      macOS junk

  [bold]NOTES[/]
    [yellow]-[/] Patterns are [bold]not[/] regex and [bold]not[/] .gitignore syntax.
    [yellow]-[/] There is no '!' un-ignore rule; you cannot re-include a match.
    [yellow]-[/] Case sensitivity follows your OS (case-insensitive on Windows)."""


def validate_dir(path):
    return (
        FileHandler.dir_is_valid(path)
        or "Directory must be valid, absolute, and readable. Try again."
    )


class FileHandler:
    def __init__(self, from_paths, to_path, compression_level, zip_password):
        self.from_paths = from_paths
        self.to_path = to_path
        self.compression_level = compression_level
        self.zip_password = zip_password
        print(from_paths, to_path, compression_level, zip_password)

    def initiate_snapshot_sequence(self):
        if (
            self.from_paths is None
            or self.to_path is None
            or self.compression_level is None
            or self.zip_password is None
        ):
            console.print(
                "[red bold]Backup cannot start. You need to set a source directory, a destination folder, a compression level (0–9), and a zip password.[/]"
            )

    @staticmethod
    def dir_is_valid(path, mode=os.R_OK):
        return os.path.isabs(path) and os.path.isdir(path) and os.access(path, mode)

    def recursively_copy_dir(self, from_dir, to_dir, ignore=None):
        # to_dir = os.path.join(to_dir, os.path.relpath(from_dir, "/"))

        if ignore is not None:
            shutil.copytree(
                from_dir,
                to_dir,
                symlinks=False,
                ignore=shutil.ignore_patterns(*ignore),
                ignore_dangling_symlinks=False,
                dirs_exist_ok=True,
            )
        else:
            shutil.copytree(
                from_dir,
                to_dir,
                symlinks=False,
                ignore=None,
                ignore_dangling_symlinks=False,
                dirs_exist_ok=True,
            )

    def compress_dir(self, src_dir, out_path, password, level=6):
        files = []
        for root, _, names in os.walk(src_dir):
            for name in names:
                files.append(os.path.join(root, name))

        with pyzipper.AESZipFile(
            out_path,
            "w",
            compression=pyzipper.ZIP_DEFLATED,
            compresslevel=level,
            encryption=pyzipper.WZ_AES,
        ) as zf:
            zf.setpassword(password.encode())
            with Progress() as progress:
                task = progress.add_task("Compressing", total=len(files))
                for f in files:
                    arcname = os.path.relpath(f, src_dir)
                    zf.write(f, arcname)
                    progress.advance(task)


class Settings:
    def __init__(self, config_path):
        self.config_path = config_path
        self.sources = set()
        self.to_dir = None
        self.compression_level = None
        self.ignore_patterns = []
        self.load()

    def load(self):
        if self.config_path.exists():
            with open(self.config_path) as f:
                data = json.load(f)
        else:
            data = {}
        self.sources = set(data.get("sources", []))
        self.to_dir = data.get("to_dir")
        self.compression_level = data.get("compression_level")
        self.ignore_patterns = data.get("ignore_patterns", [])
        return True

    def save(self):
        data = {
            "sources": sorted(self.sources),
            "to_dir": self.to_dir,
            "compression_level": self.compression_level,
            "ignore_patterns": self.ignore_patterns,
        }
        tmp = self.config_path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.config_path)
        return True

    def get_from_paths(self):
        return sorted(self.sources)

    def add_from_dir(self, path):
        if not FileHandler.dir_is_valid(path):
            return False
        self.sources.add(path)
        self.save()
        return True

    def remove_from_dir(self, path):
        self.sources.discard(path)
        self.save()
        return True

    def set_to_dir(self, path):
        if not FileHandler.dir_is_valid(path):
            return False
        self.to_dir = path
        self.save()
        return True

    def set_compression_level(self, level):
        if level < 0 or level > 9:
            return False
        self.compression_level = level
        self.save()
        return True

    def set_ignore_patterns(self, patterns_string):
        self.ignore_patterns = patterns_string.split()
        self.save()
        return True

    def reset_settings(self):
        self.sources = set()
        self.to_dir = None
        self.compression_level = None
        self.ignore_patterns = []
        self.save()
        return True


def main():
    data_dir.mkdir(parents=True, exist_ok=True)
    settings = Settings(config_path)
    # file_handler = FileHandler()
    # file_handler.compress_dir(
    #     "/Users/ritter/Documents/Vault/Projects/easybackup/from",
    #     "/Users/ritter/Documents/Vault/Projects/easybackup/tmp.zip",
    #     "123",
    # )

    console.print(
        Panel.fit(
            f"[bold bright_cyan]tuckaway[/] [dim]v0.1.0[/]\n"
            f"[dim]by[/] [cyan]Derin Alan Ritter[/] [dim]·[/] "
            f"[cyan][link=https://derinaritter.com]derinaritter.com[/link][/] [dim]·[/] "
            f"[blue]{'─' * 46}[/]\n"
            f"[dim]Data Dir   [/] [white]{data_dir}[/]\n"
            f"[dim]Databases     [/] [white]{config_path}[/]\n"
            f"[dim]Backup To  [/] [white]{settings.to_dir}[/]\n"
            f"[dim]Backing up [/] [white]{settings.get_from_paths()}[/]",
            title="[bold bright_cyan]⛁ tuckaway[/]",
            subtitle="[dim italic]No AI was used in the creation of this script.[/]",
            border_style="bright_blue",
            padding=(1, 3),
        )
    )

    while True:
        action = select(
            "Action to take: ",
            choices=[
                Separator(),
                Choice("add new directory", value="add_new_dir", shortcut_key="1"),
                Choice(
                    "delete a directory",
                    value="remove_dir",
                    shortcut_key="2",
                ),
                Choice("change backup path", value="change_to_dir", shortcut_key="3"),
                Choice(
                    "change compression level",
                    value="change_compression_level",
                    shortcut_key="4",
                ),
                Choice(
                    "change ignore patterns",
                    value="change_ignore_patterns",
                    shortcut_key="5",
                ),
                Separator(),
                Choice("start backup", value="start_backup", shortcut_key="6"),
                Separator(),
                Choice("quit", value="quit", shortcut_key="7"),
                Choice("reset ALL settings", value="reset", shortcut_key="8"),
                Separator(),
            ],
            use_shortcuts=True,
        ).ask()

        match action:
            case "add_new_dir":
                dir_path = questionary.text(
                    "Directory (absolute, with correct permissions):",
                    validate=validate_dir,
                ).ask()

                if dir_path is None:
                    continue
                if settings.add_from_dir(dir_path):
                    current = (
                        str(settings.get_from_paths()).replace("[", "").replace("]", "")
                    )
                    console.print(
                        f"[green] Directory [/]{dir_path} [green]added to list of sources to copy from.[/] "
                    )
                    console.print(
                        f"Current list of directories to be copied: {current}"
                    )
                else:
                    console.print(
                        f"[red bold]Directory [/]{dir_path}[red bold] must be valid, absolute, and readable. Try again.[/]"
                    )

            case "remove_dir":
                dir_path = questionary.text(
                    "Directory (absolute, with correct permissions):",
                    validate=validate_dir,
                ).ask()

                if dir_path is None:
                    continue
                if settings.remove_from_dir(dir_path):
                    current = (
                        str(settings.get_from_paths()).replace("[", "").replace("]", "")
                    )
                    console.print(
                        f"[green] Directory [/]{dir_path} [green]removed from list of sources to copy from.[/] "
                    )
                    console.print(
                        f"Current list of directories to be copied: {current}"
                    )

            case "change_to_dir":
                dir_path = questionary.text(
                    "Directory (absolute, with correct permissions):",
                    validate=validate_dir,
                ).ask()

                if dir_path is None:
                    continue
                if settings.set_to_dir(dir_path):
                    console.print(
                        f"[green] Directory [/]{dir_path} [green]will be the new backup location.[/] "
                    )
                else:
                    console.print(
                        f"[red bold]Directory [/]{dir_path}[red bold] must be valid, absolute, and readable. Try again.[/]"
                    )

            case "change_compression_level":
                level = questionary.text(
                    "Compression level (0-9):",
                    validate=lambda p: (
                        (p.isdigit() and 0 <= int(p) <= 9)
                        or "Compression level must be an integer between 0 and 9."
                    ),
                ).ask()

                if level is None:
                    continue
                if settings.set_compression_level(int(level)):
                    console.print(
                        f"[green] Compression level [/]{level} [green]will be used.[/] "
                    )
                else:
                    console.print(
                        f"[red bold]Compression level [/]{level}[red bold] must be an integer between 0 and 9.[/]"
                    )

            case "change_ignore_patterns":
                console.print(IGNORE_HELP)
                patterns = questionary.text(
                    "Ignore patterns (space separated):",
                ).ask()

                if patterns is None:
                    continue
                if settings.set_ignore_patterns(patterns):
                    console.print(
                        f"[green] Ignore patterns [/]{', '.join(settings.ignore_patterns)} [green]has been set.[/] "
                    )

            case "start_backup":
                password = questionary.password(
                    "Zip Password:",
                    validate=lambda p: len(p) > 0 or "Password cannot be empty.",
                ).ask()

                file_handler = FileHandler(
                    settings.sources,
                    settings.to_dir,
                    settings.compression_level,
                    password,
                )
                file_handler.initiate_snapshot_sequence()

            case "quit":
                raise SystemExit(0)
            case "reset":
                settings.reset_settings()
                console.print(
                    "[green]Settings and backup directories have been reset.[/]"
                )
                raise SystemExit(0)
            case _:
                raise SystemExit(0)

        console.rule(characters="=", style="grey")


if __name__ == "__main__":
    main()
