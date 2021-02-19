import sys

from . import cli

if __name__ == '__main__':
    with cli.confirm_close_on_exception():
        sys.exit(cli.main())
