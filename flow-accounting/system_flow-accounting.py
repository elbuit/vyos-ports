#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

import sys
import os

import jinja2
import copy

from vyos.config import Config
from vyos import ConfigError

config_file = r'/etc/pmacct/uacctd.conf'
networks_file = '/etc/pmacct/networks.lst'
# Please be careful if you edit the template.
config_tmpl = """
daemonize: true 
promisc:   false 
pidfile: /var/run/uacctd.pid 
imt_path:  /tmp/uacctd.pipe
imt_mem_pools_number: 169; # number of memory pool descriptors
uacctd_group: 2 uacctd_nl_size: 2097152 #2M 
snaplen: 4096 
refresh_maps: true 
pre_tag_map: /etc/pmacct/int_map 
plugin_pipe_size: {{ pipe_size*1024*1024 }}
plugin_buffer_size: {{pipe_size*1024 }}
aggregate: tag,src_mac,dst_mac,vlan,src_host,dst_host,
src_port,dst_port,proto,tos,flows
{% if networks -%}
,src_as,dst_as 
networks_file: {{networks_file}} {% endif -%} 
"""

default_config_data = {
    'interfaces': [],
    'netflow': [],
    'sflow': [],

}


def get_config():
    flowacc = copy.deepcopy(default_config_data)

    conf = Config()

    if not conf.exists('system flow-accounting'):
        return None
    else:
        conf.set_level('system flow-accounting')
    if conf.exists('buffer-size'):
        flowacc['buffer-size'] = conf.return_values('buffer-size')

    if conf.exists('disable-imt'):
        flowacc['disable-imt'] = conf.return_values('disable-imt')
    if conf.exists('syslog-facility'):
        flowacc['syslog-facility'] = conf.return_values('syslog-facility')

    for node in conf.list_nodes('interface'):
        interface = {
            "if_name": node
        }
        flowacc['interfaces'].append(interface)

    if conf.exists('netflow'):
        netflow = {}
        if conf.exists('netflow engine-id'):
            netflow['engine-id'] = conf.return_values('netflow engine-id')
        if conf.exists('netflow max-flows'):
            netflow['max-flows'] = conf.return_values('netflow max-flows')
        if conf.exists('netflow sampling-rate'):
            netflow['sampling-rate'] = conf.return_values('netflow '
                                                          'sampling-rate')
        if conf.exists('netflow source-ip'):
            netflow['source-ip'] = conf.return_values('netflow source-ip')
        # Timeouts
        if conf.exists('netflow timeout expiry-interval'):
            netflow['expiry-interval'] = conf.return_values('netflow timeout '
                                                            'expiry-interval')
        if conf.exists('netflow timeout flow-generic'):
            netflow['flow-generic'] = conf.return_values('netflow timeout '
                                                         'flow-generic')
        if conf.exists('netflow timeout icmp'):
            netflow['icmp'] = conf.return_values('netflow timeout icmp')
        if conf.exists('netflow timeout max-active-life'):
            netflow['max-active-life'] = conf.return_values('netflow timeout '
                                                            'max-active-life')
        if conf.exists('netflow timeout tcp-fin'):
            netflow['tcp-fin'] = conf.return_values('netflow timeout tcp-fin')
        if conf.exists('netflow timeout tcp-generic'):
            netflow['tcp-generic'] = conf.return_values('netflow timeout '
                                                        'tcp-generic')
        if conf.exists('netflow timeout tcp-rst'):
            netflow['tcp-rst'] = conf.return_values('netflow timeout tcp-rst')
        if conf.exists('netflow timeout udp'):
            netflow['udp'] = conf.return_values('netflow timeout udp')
        if conf.exists('version'):
            flowacc['version'] = conf.return_values('version')

        for node in conf.list_nodes('netflow server'):
            server = {
                "ip": node
            }
            if conf.return_values('server {0} port'.format(node)):
                port = conf.return_values('server {0} port'.format(node))
                server['port'] = port
            netflow['servers'].append(server)

        flowacc['netflow'] = netflow

    if conf.exists('sflow'):
        sflow = {}
        if conf.exists('sflow agent-address'):
            sflow['agent-address'] = conf.return_values('sflow agent-address')
        if conf.exists('sflow sampling-rate'):
            sflow['sampling-rate'] = conf.return_values('sflow sampling-rate')
        if conf.exists(''):
            sflow[''] = conf.return_values('')
        for node in conf.list_nodes('sflow server'):
            server = {
                "ip": node
            }
            if conf.return_values('server {0} port'.format(node)):
                port = conf.return_values('server {0} port'.format(node))
                server['port'] = port
            sflow['servers'].append(server)
        flowacc['sflow'] = sflow

    if os.path.exists(networks_file):
        flowacc['networks_file'] = networks_file

    return flowacc


def verify(flowacc):
    # bail out early - looks like removal from running config
    if flowacc is None:
        return None

    if not len(flowacc['interfaces']):
        raise ConfigError('No interfaces configured')

    if flowacc['netflow'] and not len(flowacc['netflow']['servers']):
        raise ConfigError('At least one netflow server should be configured')

    if flowacc['sflow'] and not len(flowacc['sflow']['servers']):
        raise ConfigError('At least one sflow server should be configured')

    return None


def generate(flowacc):
    # bail out early - looks like removal from running config
    if flowacc is None:
        return None

    tmpl = jinja2.Template(config_tmpl)
    config_text = tmpl.render(flowacc)
    with open(config_file, 'w') as f:
        f.write(config_text)

    return None


def apply(flowacc):
    if flowacc is not None:
        os.system('sudo systemctl restart uacctd.service')
    else:
        # flowacc support is removed in the commit
        os.system('sudo systemctl stop uacctd.service')
        os.unlink(config_file)

    return None


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
