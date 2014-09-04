#!/usr/bin/env python
'''class for parsing PBS options'''

from argparse import ArgumentParser
import re, validate_email

from vsc.utils import walltime2seconds, size2bytes
from vsc.utils import InvalidWalltimeError


class PbsOptionParser(object):
    '''Parser for PBS options, either command line or directives'''

    def __init__(self, job):
        '''constructor'''
        self._job = job
        self._arg_parser = ArgumentParser()
        self._arg_parser.add_argument('-A')
        self._arg_parser.add_argument('-j')
        self._arg_parser.add_argument('-k')
        self._arg_parser.add_argument('-l', action='append')
        self._arg_parser.add_argument('-m')
        self._arg_parser.add_argument('-M')
        self._arg_parser.add_argument('-N')
        self._arg_parser.add_argument('-q')
        self._events = []

    @property
    def events(self):
        '''returns events collected during parse'''
        return self._events

    def reg_event(self, event, extra={}):
        '''register an event when it occurs'''
        self._events.append({'event': event,
                             'extra': extra})

    def parse_args(self, option_line):
        '''parse options string'''
        self._events = []
        args = self._arg_parser.convert_arg_line_to_args(option_line)
        options, rest = self._arg_parser.parse_known_args(args)
        for option, value in options.__dict__.items():
            if value:
                self.handle_option(option, value)

    def handle_option(self, option, value):
        '''option dispatch method'''
        if option == 'A':
            self.check_A(value.strip())
        elif option == 'j':
            self.check_j(value.strip())
        elif option == 'k':
            self.check_k(value.strip())
        elif option == 'l':
            self.check_l(value)
        elif option == 'm':
            self.check_m(value.strip())
        elif option == 'M':
            self.check_M(value.strip())
        elif option == 'N':
            self.check_N(value.strip())
        elif option == 'q':
            self.check_q(value.strip())

    def check_A(self, val):
        '''check whether a valid project name was specified'''
        if re.match(r'[A-Za-z]\w*$', val):
            self._job.project = val
        else:
            self.reg_event('invalid_project_name', {'val': val})

    def check_q(self, val):
        '''check whether a valid queue name was specified'''
        if re.match(r'[A-Za-z]\w*$', val):
            self._job.queue = val
        else:
            self.reg_event('invalid_queue_name', {'val': val})

    def check_j(self, val):
        '''check -j option, vals can be oe, eo, n'''
        if val == 'oe' or val == 'eo' or val == 'n':
            self._job.join = val
        else:
            self.reg_event('invalid_join', {'val': val})

    def check_k(self, val):
        '''check -k option, val can be e, o, oe, eo, or n'''
        if re.match(r'^[eo]+$', val) or val == 'n':
            self._job.keep = val
        else:
            self.reg_event('invalid_join', {'val': val})

    def check_m(self, val):
        '''check -m option, val can be any combination of b, e, a, or n'''
        if re.match(r'(?:^[bea]{1,3}$)|(?:^n$)', val):
            self._job.mail_events = val
        else:
            self.reg_event('invalid_mail_event', {'val': val})

    def check_M(self, val):
        '''check -M option'''
        self._job.mail_addresses = val.split(',')
        for address in self._job.mail_addresses:
            if not validate_email.validate_email(address):
                self.reg_event('invalid_mail_address', {'address': address})

    def check_N(self, val):
        '''check -N is a valid job name'''
        if re.match(r'[A-Za-z]\w{,14}$', val):
            self._job.name = val
        else:
            self.reg_event('invalid_job_name', {'val': val})

    def check_l(self, vals):
        '''check and handle resource options'''
        resource_spec = {}
# there can be multiple -l options on one line or on the command line
        for val_str in (x.strip() for x in vals):
# values can be combined by using ','
            for val in (x.strip() for x in val_str.split(',')):
                if val.startswith('walltime=') or val.startswith('cput='):
                    attr_name, attr_value = val.split('=')
                    try:
                        seconds = walltime2seconds(attr_value)
                        resource_spec[attr_name] = seconds
                    except InvalidWalltimeError as error:
                        self.reg_event('invalid_{0}_format'.format(attr_name),
                                       {'time': attr_value})
                elif val.startswith('mem=') or val.startswith('pmem='):
                    attr_name, attr_value = val.split('=')
                    match = re.match(r'(\d+)([kmgt])[bw]', attr_value)
                    if match:
                        amount = int(match.group(1))
                        order = match.group(2)
                        resource_spec[attr_name] = size2bytes(amount, order)
                    else:
                        self.reg_event('invalid_{0}_format'.format(attr_name),
                                       {'size': attr_value})
                elif val.startswith('nodes='):
                    attr_name, attr_value = val.split('=', 1)
# if present, multiple node specifications are separated by '+'
                    node_spec_strs = attr_value.split('+')
                    node_specs = []
                    for node_spec_str in node_spec_strs:
                        node_spec = {'features': []}
                        spec_strs = node_spec_str.split(':')
# if a node spec starts with a number, that's the number of nodes,
# otherwise it can be a hostname or a feature, but number of nodes is 1
                        if spec_strs[0].isdigit():
                            node_spec['nodes'] = int(spec_strs[0])
                        else:
                            node_spec['nodes'] = 1
# note that this might be wrong, it may actually be a feature, but
# that is a semantic check, not syntax
                            node_spec['host'] = spec_strs[0]
# now deal with the remaining specifications, ppn, gpus and features
                        for spec_str in spec_strs[1:]:
                            if (spec_str.startswith('ppn=') or
                                spec_str.startswith('gpus=')):
                                key, value = spec_str.split('=')
                                if value.isdigit():
                                    node_spec[key] = int(value)
                                else:
                                    self.reg_event('{0}_no_number'.format(key),
                                                   {'number': value})
                            else:
                                node_spec['features'].append(spec_str)
                        node_specs.append(node_spec)
                    resource_spec['nodes'] = node_specs
                else:
                    self.reg_event('unknown_resource_spec',{'spec': val})
        self._job.add_resource_specs(resource_spec)

