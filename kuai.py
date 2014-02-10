import json
import pystache
from collections import defaultdict
import sys

class compiler(object):
    def __init__(self, topology_file, controller_file, under=True):
        self.bound = 1
        self.under = under
        self.topology = json.load(open(topology_file))
        self.rules_template = open('rules.text').read()
        self.controller_template = open(controller_file).read()
        self.client_single_switch = True # this will be set by get_clients
        self.clients = self.get_clients()
        self.switches = self.get_switches()
        
        self.packet_decls_text = ''
        self.controller_client_decls_text = ''
        self.client_text = ''
        self.controller_text = ''
        self.controller_client_rules_text = ''
        self.controller_client_startstate_text = ''
        self.invariant_text = ''
        self.check_dropped_text = ''
        self.check_forwarded_text = ''
        self.render()

    def render(self):
        rendering = {
            'bound': self.bound,
            'num_clients': self.num_clients(),
            'data_queue_size': 24,
            'control_queue_size': 16, #TODO: get the right value here
            'switch_rules_count': 12, #TODO: get the right value here
            'rule_fields': self.rule_fields(),
            'clients': self.clients,
            'switches': self.switches,
            'switch_counter': self.should_use_switch_counter(),
            'drop_packet_tracking': self.should_track_dropped_packets(),
            'forward_packet_tracking': self.should_track_forwarded_packets(),
            'num_switches': len(self.switches),
            'data_packet_fields': self.data_packet_fields(),

            'packet_decls': self.append_packet_decls_text,
            'controller_client_decls': self.append_controller_client_decls_text,
            'client_procs': self.append_client_text,
            'controller_procs': self.append_controller_text,
            'controller_client_rules': self.append_controller_client_rules_text,
            'controller_client_startstate': self.append_controller_client_startstate_text,
            'invariant': self.append_invariant_text,
            'check_dropped_packet': self.append_check_dropped_text,
            'check_forwarded_packet': self.append_check_forwarded_text,

            'num_ports': self.num_ports(),
            'switch_ids_string': self.switch_ids_string(), #{{mustache}} cannot remove trailing comma easily
            'client_ids_string': self.client_ids_string(),
            'client_single_switch': self.client_single_switch
        }
        
        # do not escape HTML,  just output raw text
        renderer = pystache.Renderer(escape=lambda u: u)
        controller_client_text = renderer.render(self.controller_template, rendering)
        
        if controller_client_text.strip() != '':
            print >> sys.stderr, "Controller file should emit nothing, but got %s" % controller_client_text
            assert(False)

        rendering['packet_decls_text'] = self.packet_decls_text
        rendering['controller_client_decls_text'] = self.controller_client_decls_text
        rendering['client_text'] = self.client_text
        rendering['controller_text'] = self.controller_text
        rendering['controller_client_rules_text'] = self.controller_client_rules_text
        rendering['controller_client_startstate_text'] = self.controller_client_startstate_text
        rendering['invariant_text'] = self.invariant_text
        rendering['check_dropped_text'] = self.check_dropped_text
        rendering['check_forwarded_text'] = self.check_forwarded_text
        print renderer.render(self.rules_template, rendering)

    def num_ports(self):
        return max([switch['ports'] for switch in self.topology['switches']])
        
    def append_packet_decls_text(self, text):
        self.packet_decls_text = self.packet_decls_text + text
        return ''

    def append_controller_client_decls_text(self, text):
        self.controller_client_decls_text += text
        return ''

    def append_controller_text(self, text):
        self.controller_text += text
        return ''

    def append_controller_client_rules_text(self, text):
        self.controller_client_rules_text += text
        return ''

    def append_client_text(self, text):
        self.client_text += text
        return ''

    def append_controller_client_startstate_text(self, text):
        self.controller_client_startstate_text += text
        return ''

    def append_invariant_text(self, text):
        self.invariant_text += text
        return ''

    def append_check_dropped_text(self, text):
        self.check_dropped_text = self.check_dropped_text + text
        return ''

    def append_check_forwarded_text(self, text):
        self.check_forwarded_text = self.check_forwarded_text + text
        return ''

    def should_use_switch_counter(self):
        return self.topology.has_key('switch_counter') and self.topology['switch_counter']

    def should_track_dropped_packets(self):
        return self.topology.has_key('drop_packet_tracking') and self.topology['drop_packet_tracking']

    def should_track_forwarded_packets(self):
        return self.topology.has_key('forward_packet_tracking') and self.topology['forward_packet_tracking']

    def data_packet_fields(self):
        built_in = [{'field_name': 'port', 'field_type': "-1..%d" % self.num_ports()}]

        return built_in + [{'field_name': key, 'field_type': value} for key, value in self.topology['packet'].items()]

    def num_clients(self):
        return self.topology['clients']

    def switch_ids_string(self):
        return ', '.join("%s_id" % switch['id'] for switch in self.topology['switches'])

    def client_ids_string(self):
        return ', '.join("%s_id" % switch['id'] for switch in self.topology['clients'])
                    
    def rule_fields(self):
        return [{'field_name': key, 'field_type': value} for key, value in self.topology['rule_match_fields'].items()]

    # adds information about fan out
    def build_client_communications(self, client):
        if client.has_key('contacts'):
            client['contacts'] = [{'dest': contact} for contact in client['contacts']]
        else:
            client['contacts'] = [{'dest': dest_client['id']} for dest_client in self.topology['clients'] if client['id'] != dest_client['id']]
    
    # adds connecting switch information if possible
    def build_client_switch(self, client):
        client_name = client['id']
        
        for src, dest in self.topology['connections']:
            src_node, src_port = src.items()[0]
            dest_node, dest_port = dest.items()[0]
            if src_node == client_name or dest_node == client_name:
                switch = (src_node if dest_node == client_name else dest_node)
                switch_port = (src_port if dest_node == client_name else dest_port)
                if client.has_key('connecting_switch'):
                    self.client_single_switch = False
                client['connecting_switch'] = switch
                client['connecting_switch_port'] = switch_port
        
    def get_clients(self):
        for client in self.topology['clients']:
            self.build_client_communications(client)
            self.build_client_switch(client)
            
        return self.topology['clients']

    def is_client(self, node_name):
        try:
            node_name.index('client')
            return True
        except ValueError:
            return False
            
    def is_switch(self, node_name):
        try:
            node_name.index('switch')
            return True
        except ValueError:
            return False
    
    def build_connections(self, switch):
        connections = []
        for src, dest in self.topology['connections']:
            src_node, src_port = src.items()[0]
            dest_node, dest_port = dest.items()[0]
            src_queue_proc = ("client_packet_received" if not self.is_switch(src_node) else "enqueue_data")
            dest_queue_proc = ("client_packet_received" if not self.is_switch(dest_node) else "enqueue_data")
            src_queue_arg = ("%s_id" if not self.is_switch(src_node) else "switches[%s_id].data_queue") % src_node
            dest_queue_arg = ("%s_id" if not self.is_switch(dest_node) else "switches[%s_id].data_queue") % dest_node
            if src_node == switch['id']:
                connections.append({'src_port': src_port,
                                    'dest_queue_proc': dest_queue_proc,
                                    'dest_queue_arg': dest_queue_arg,
                                    'dest_port': dest_port})
            elif dest_node == switch['id']:
                connections.append({'src_port': dest_port,
                                    'dest_queue_proc': src_queue_proc,
                                    'dest_queue_arg': src_queue_arg,
                                    'dest_port': src_port})
                
        return connections
            
    # mutating switch
    def build_switch(self, switch):
        switch['connections'] = self.build_connections(switch)
        return switch
        
    def get_switches(self):
        return [self.build_switch(switch) for switch in self.topology['switches']]
                
            
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Needs a directory name"
    else:
        directory = sys.argv[1]
        compiler("%s/topology" % directory, "%s/controller.text" % directory, under=False)
