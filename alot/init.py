#!/usr/bin/env python
import sys
import logging
import os

import settings
import ConfigParser
from account import AccountManager
from db import DBManager
from ui import UI
import alot.commands as commands
from commands import *
from alot.commands import CommandParseError
import alot

from twisted.python import usage


class SubcommandOptions(usage.Options):
    optFlags = []

    def parseArgs(self, *args):
        self.args = args

    def as_argparse_opts(self):
        optstr = ''
        for k, v in self.items():
            # flags translate int value 0 or 1..
            if k in [a[0] for a in self.optFlags]:  # if flag
                optstr += ('--%s ' % k) * v
            else:
                if v is not None:
                    optstr += '--%s \'%s\' ' % (k, v)
        return optstr

    def opt_version(self):
        print alot.__version__
        sys.exit(0)


class ComposeOptions(SubcommandOptions):
    optParameters = [
                ['sender', '', None, 'From line'],
                ['subject', '', None, 'subject line'],
                ['cc', '', None, 'copy to'],
                ['bcc', '', None, 'blind copy to'],
                ['template', '', None, 'path to template file'],
                ['attach', '', None, 'files to attach'],
            ]
    optFlags = [
            ['omit_signature', '', 'do not add signature'],
            ]

    def parseArgs(self, *args):
        SubcommandOptions.parseArgs(self, *args)
        self['to'] = ' '.join(args) or None


class SearchOptions(SubcommandOptions):
    accepted = ['oldest_first', 'newest_first', 'message_id', 'unsorted']

    def colourint(val):
        if val not in accepted:
            raise ValueError("Unknown sort order")
        return val
    colourint.coerceDoc = "Must be one of " + str(accepted)
    optParameters = [
                ['sort', 'newest_first', None, 'Sort order'],
            ]


class Options(usage.Options):
    optFlags = [["read-only", "r", 'open db in read only mode'], ]

    def colourint(val):
        val = int(val)
        if val not in [1, 16, 256]:
            raise ValueError("Not in range")
        return val
    colourint.coerceDoc = "Must be 1, 16 or 256"

    def debuglogstring(val):
        if val not in ['error', 'debug', 'info', 'warning']:
            raise ValueError("Not in range")
        return val
    debuglogstring.coerceDoc = "Must be one of debug,info,warning or error"

    optParameters = [
            ['config', 'c', '~/.config/alot/config', 'config file'],
            ['notmuch-config', 'n', '~/.notmuch-config', 'notmuch config'],
            ['colour-mode', 'C', 256, 'terminal colour mode', colourint],
            ['mailindex-path', 'p', None, 'path to notmuch index'],
            ['debug-level', 'd', 'info', 'debug log', debuglogstring],
            ['logfile', 'l', '/dev/null', 'logfile'],
    ]
    search_help = "start in a search buffer using the querystring provided "\
                  "as parameter. See the SEARCH SYNTAX section of notmuch(1)."

    subCommands = [['search', None, SearchOptions, search_help],
                   ['compose', None, ComposeOptions, "compose a new message"]]

    def opt_version(self):
        print alot.__version__
        sys.exit(0)


def main():
    # interpret cml arguments
    args = Options()
    try:
        args.parseOptions()  # When given no argument, parses sys.argv[1:]
    except usage.UsageError, errortext:
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)

    # locate alot config files
    configfiles = [
        os.path.join(os.environ.get('XDG_CONFIG_HOME',
                                    os.path.expanduser('~/.config')),
                     'alot', 'config'),
        os.path.expanduser('~/.alot.rc'),
    ]
    if args['config']:
        expanded_path = os.path.expanduser(args['config'])
        if not os.path.exists(expanded_path):
            sys.exit('File %s does not exist' % expanded_path)
        configfiles.insert(0, expanded_path)

    # locate notmuch config
    notmuchfile = os.path.expanduser(args['notmuch-config'])

    try:
        # read the first alot config file we find
        for configfilename in configfiles:
            if os.path.exists(configfilename):
                settings.config.read(configfilename)
                break  # use only the first

        # read notmuch config
        settings.notmuchconfig.read(notmuchfile)

    except ConfigParser.Error, e:  # exit on parse errors
        sys.exit(e)

    # logging
    ## reset
    root_logger = logging.getLogger()
    for log_handler in root_logger.handlers:
        root_logger.removeHandler(log_handler)
    root_logger = None
    ## setup
    numeric_loglevel = getattr(logging, args['debug-level'].upper(), None)
    logfilename = os.path.expanduser(args['logfile'])
    logformat = '%(levelname)s:%(module)s:%(message)s'
    logging.basicConfig(level=numeric_loglevel, filename=logfilename,
                        format=logformat)

    #logging.debug(commands.COMMANDS)
    # get ourselves a database manager
    dbman = DBManager(path=args['mailindex-path'], ro=args['read-only'])

    #accountman
    aman = AccountManager(dbman, settings.config)

    # get initial searchstring
    try:
        if args.subCommand == 'search':
            query = ' '.join(args.subOptions.args)
            cmdstring = 'search %s %s' % (args.subOptions.as_argparse_opts(),
                                          query)
            cmd = commands.commandfactory(cmdstring, 'global')
        elif args.subCommand == 'compose':
            cmdstring = 'compose %s' % args.subOptions.as_argparse_opts()
            cmd = commands.commandfactory(cmdstring, 'global')
        else:
            default_commandline = settings.config.get('general',
                                                      'initial_command')
            cmd = commands.commandfactory(default_commandline, 'global')
    except CommandParseError, e:
        sys.exit(e)

    # set up and start interface
    UI(dbman,
       aman,
       cmd,
       args['colour-mode'],
    )

if __name__ == "__main__":
    main()
