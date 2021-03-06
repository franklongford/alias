import click
import os
import sys
from subprocess import check_call

DEFAULT_PYTHON_VERSION = "3.6"
PYTHON_VERSIONS = ["3.6"]
APP_REPO = os.path.abspath('.')

EDM_CORE_DEPS = [
    'Click==7.0-1'
]
EDM_DEV_DEPS = [
    "flake8==3.7.7-1",
    "coverage==4.3.4-1",
    "mock==2.0.0-3"
]

CONDA_CORE_DEPS = [
    'Click'
]
CONDA_DEV_DEPS = [
    "flake8==3.7.7",
    "mock==2.0.0"
]

DOCS_DEPS = []
PIP_DEPS = []


def remove_dot(python_version):
    return "".join(python_version.split("."))


def get_env_name(python_version):
    return f"alias-py{remove_dot(python_version)}"


def edm_run(env_name, command, cwd=None):
    check_call(
        ['edm', 'run', '-e', env_name, '--'] + command,
        cwd=cwd
    )


@click.group()
def cli():
    pass


python_version_option = click.option(
    '--python-version',
    default=DEFAULT_PYTHON_VERSION,
    type=click.Choice(PYTHON_VERSIONS),
    show_default=True,
    help="Python version for environment"
)


@cli.command(
    name="build-env",
    help="Creates the edm execution environment")
@click.option(
    '--edm', is_flag=True, default=False,
    help='Toggles EDM build'
)
@click.option(
    '--conda', is_flag=True, default=False,
    help='Toggles Conda build'
)
@python_version_option
def build_env(python_version, edm, conda):
    env_name = get_env_name(python_version)

    if edm:
        check_call([
            "edm", "env", "remove", "--purge", "--force",
            "--yes", env_name]
        )
        check_call(
            ["edm", "env", "create", "--version",
             python_version, env_name]
        )

        check_call([
            "edm", "install", "-e", env_name, "--yes"]
            + EDM_CORE_DEPS + EDM_DEV_DEPS + DOCS_DEPS
        )

    elif conda:
        check_call([
            "conda", "remove", "--all", "--force",
            "--yes", '-n', env_name]
        )

        check_call(
            ["conda", "create", f"python={python_version}",
             "-n", env_name, '-y']
        )

        check_call([
           "conda", "install", "-n", env_name, "--yes"]
            + CONDA_CORE_DEPS + CONDA_DEV_DEPS + DOCS_DEPS
                   )
    else:
        print('Include flag to specify environment '
              'package manager, either EDM (--edm) or '
              'Conda (--conda)')


@cli.command(
    name="install",
    help=('Creates the execution binary inside the'
          ' production environment')
)
@click.option(
    '--edm', is_flag=True, default=False,
    help='Toggles EDM installation'
)
@click.option(
    '--conda', is_flag=True, default=False,
    help='Toggles Conda installation'
)
@python_version_option
def install(python_version, edm, conda):

    env_name = get_env_name(python_version)
    if edm:
        print('Installing  to edm environment')
        edm_run(env_name, ['pip', 'install', '-e', '.'])
    elif conda:
        print(f'Installing {get_env_name(python_version)}'
              f' to conda environment')
        check_call(['pip', 'install', '-e', '.'])
    else:
        print(f'Installing {get_env_name(python_version)}'
              f' to local environment')
        native_python_version = sys.version_info

        for i in range(2):
            try:
                target_version = int(python_version.split('.')[i])
                native_version = int(native_python_version[i])
                assert native_version >= target_version
            except AssertionError:
                print('native python version does not meet requirements'
                      f'({python_version})')

        command = input('Enter the installation command for your local '
                        'package manager: ')
        check_call(
            command.split()
            + CONDA_CORE_DEPS + CONDA_DEV_DEPS + DOCS_DEPS
        )
        check_call(['pip', 'install', '-e', '.'])


@cli.command(help="Runs the coverage")
@python_version_option
def coverage(python_version):

    env_name = get_env_name(python_version)

    edm_run(
        env_name,
        ["coverage", "run", "-m", "unittest", "discover"]
    )

    edm_run(
        env_name,
        ["coverage", "report", "-m"]
    )

    if os.path.exists('.coverage'):
        os.remove('.coverage')


@cli.command(help="Run flake (dev)")
@click.option(
    '--edm', is_flag=True, default=False,
    help='Toggles EDM call'
)
@python_version_option
def flake8(python_version, edm):

    env_name = get_env_name(python_version)
    if edm:
        edm_run(env_name, ["flake8", "."])
    else:
        check_call(["flake8", "."])


@cli.command(help="Run the unit tests")
@click.option(
    '--edm', is_flag=True, default=False,
    help='Toggles EDM call'
)
@python_version_option
def test(python_version, edm):

    env_name = get_env_name(python_version)
    if edm:
        edm_run(env_name,
                ["python", "-m", "unittest", "discover", "-v"])
    else:
        check_call(
                ["python", "-m", "unittest", "discover", "-v"])


if __name__ == "__main__":
    cli()
