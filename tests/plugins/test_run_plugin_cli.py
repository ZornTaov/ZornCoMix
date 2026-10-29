#run_plugin.py from the command line, the way someone without the web page sets plugins up: --list says what is
#there and what each asks for, a folder that cannot be a plugin is said so rather than skipped, and --install
#and --update fetch one from its repository.
import os

from conftest import run
from test_plugin_install import needs_git, repository
from test_plugins import install


def plugin_cli(library, *args):
    done = run("run_plugin.py", *args, cwd=library)
    return done.returncode, done.stdout + done.stderr


def test_a_library_with_no_plugins_says_where_they_go(library, config):
    code, said = plugin_cli(library, "--list")
    assert code == 0 and "No plugins in" in said and "plugin.json" in said, said


def test_the_list_names_each_plugin_its_settings_and_any_that_cannot_be_used(library, config):
    install(config)
    broken = os.path.join(str(config), "plugins", "broken")
    os.makedirs(broken)
    with open(os.path.join(broken, "plugin.json"), "w", encoding="utf-8") as f:
        f.write("{ this is not json")
    code, said = plugin_cli(library, "--list")
    assert code == 0, said
    assert said.startswith("example  ("), said
    assert "    url " in said, "the plugin's settings are listed under it: " + said
    assert "CANNOT BE USED" in said and "broken" in said, said


@needs_git
def test_a_plugin_is_installed_and_updated_from_its_repository(library, config, tmp_path):
    source = repository(tmp_path)
    code, said = plugin_cli(library, "--install", source.as_uri())
    assert code == 0, said
    assert os.path.isfile(os.path.join(str(config), "plugins", "example", "plugin.json"))
    code, said = plugin_cli(library, "--list")
    assert said.startswith("example  ("), said
    code, said = plugin_cli(library, "--update", "example")
    assert code == 0, said


def test_installing_from_nowhere_is_refused_with_why(library, config, tmp_path):
    code, said = plugin_cli(library, "--install", (tmp_path / "nothing-here").as_uri())
    #git says its own piece first, and the error after it
    assert code == 2 and "ERROR: git clone failed" in said, said
    code, said = plugin_cli(library, "--update", "no-such-plugin")
    assert code == 2 and said.startswith("ERROR:"), said
