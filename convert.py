#!/usr/bin/env python3

import os
import sys
import shutil
import yaml
import rospkg

types_convert = {}
types_convert['time'] = 'builtin_interfaces/Time'
types_convert['Header'] = 'std_msgs/Header'
types_convert['rosgraph_msgs/Log'] = 'rcl_interfaces/Log'

class Interface:
    def __init__(self, filename, package_name):
        self.filename = os.path.basename(filename)
        self.depends = set()
        self.types = set()
        self.name = self.filename[:-4]
        
        print('\nParsing ' + self.filename)
        
        # changes to ROS 2 field names
        self.fields_1_to_2 = {}
        
        fields = []
        
        with open(filename) as f:
            content = f.read().splitlines()
        self.content = []
        for line in content:
            
            if line.strip().startswith('#') or ' ' not in line:
                self.content.append(line)
                continue    
                
            line_spt = line.split()
            type_1 = line_spt[0]
            field_1= line_spt[1]
            
            if '=' in field_1:
                field_1, info = field_1.split('=')
                if len(line_spt) == 2:
                    line_spt.append('=' + info)
                else:
                    line_spt[2] = '=' + info + line_spt[2]
                
            # adapt field name
            field_2 = field_1        
            if len(line_spt) > 2 and line_spt[2].startswith('='):
                # constant should be upper case
                if not field_1.isupper():
                    field_2 = field_1.upper()
            else:
                # non-constant should be snake_case
                if not field_1.islower():
                    field_2 = ''.join(s.islower() and s or '_'+s.lower() for s in field_1).strip('_')
                    
            # adapt field type
            type_2 = type_1
            if type_2 in types_convert:
                type_2 = types_convert[type_2]
            
            if field_2.islower():
                if field_2 != field_1:
                    self.fields_1_to_2[field_1] = field_2
                else:
                    fields.append(field_1)
                
            if package_name in type_2:
                type_2 = type_2.split('/')[1]
            self.types.add(type_2.strip('[]'))
            
            info = field_2.islower() and 'variable' or 'constant'
            if type_2 != type_1 or field_2 != field_1:
                print(' {} field {} {} -> changed to {} {}'.format(info, type_1, field_1, type_2, field_2))
            #else:
            #    print(' {} field {} {} -> ok'.format(info, type_1, field_1))
                
            if '/' in type_2:
                self.depends.add(type_2.split('/')[0])
                
            self.content.append('{} {} {}'.format(type_2, field_2, ' '.join(line_spt[2:])))
        self.content = '\n'.join(self.content)
        
        if self.fields_1_to_2:
            for field in fields:
                self.fields_1_to_2[field] = field
            
    def save(self, dst):
        dst = os.path.join(dst, self.filename[-3:])
        if not os.path.exists(dst):
            os.makedirs(dst)
        
        with open(os.path.join(dst, self.filename), 'w') as f:
            f.write(self.content)
            
    def rep(self):
        return '"{}/{}"'.format(self.filename[-3:], self.filename)
                                
                                
def usage(s = ''):
    if s:
        print(s)
    
    print('Run this script by giving the ROS 1 message package path and the ROS 2 workspace')
    sys.exit(0)

if __name__ == '__main__':

    if len(sys.argv) != 3:
        usage()
    
    src = sys.argv[1]
    dst = sys.argv[2]
    
    if not os.path.exists(src):
        # try by package name
        rospack = rospkg.RosPack()
        try:
            src = rospack.get_path(src)
        except:
            pass
        if not os.path.exists(src):
            usage('ROS 1 package does not exist')
    if not os.path.exists(dst):
        usage('ROS 2 destination does not exist')
        
    if 'src' in os.listdir(dst):
        dst = os.path.join(dst, 'src')

    package_name = os.path.basename(src.rstrip(os.path.sep))
    dst = os.path.join(dst, package_name)
    
    msgs = []
    depends = set()
    
    if os.path.exists(dst):
        shutil.rmtree(dst)
    
    for msg_type in ('msg','srv'):
        src_dir = os.path.join(src, msg_type)
        if os.path.exists(src_dir):
            msgs += [Interface(os.path.join(src_dir, f), package_name) for f in os.listdir(src_dir)]
    
    if not msgs:
        usage('No interfaces defined in {}'.format(src)) 

    # Create message files    
    for msg in msgs:
        msg.save(dst)
        for d in msg.depends:
            depends.add(d)
            

    # Create CMakeLists and package.xml
    template_path = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(template_path, 'CMakeLists.txt.template')) as f:
        cmake = f.read()
    with open(os.path.join(template_path, 'package.xml.template')) as f:
        pkg_xml = f.read()
    
    cmake = cmake.replace('<package>', package_name)
    pkg_xml = pkg_xml.replace('<package>', package_name)
    
    find_depends = []
    xml_depends = []
    for depend in depends:
        find_depends.append('find_package({} REQUIRED)'.format(depend))
        for key in ('build', 'exec'):
            xml_depends.append('<{key}_depend>{depend}</{key}_depend>'.format(key = key, depend = depend))
        
    cmake = cmake.replace('<find_depends>', '\n'.join(find_depends))
    pkg_xml = pkg_xml.replace('<build_exec_depends>', '\n  '.join(sorted(xml_depends)))
    if depends:
        cmake = cmake.replace('<msgs_depends>', 'DEPENDENCIES ' + ' '.join(depends))
    else:
        cmake = cmake.replace('<msgs_depends>', '')
    cmake = cmake.replace('<msgs>', '  \n'.join(msg.rep() for msg in msgs))
    
    mapping_rules = []
    for msg in msgs:
        if msg.fields_1_to_2:
            mapping_rules.append({'ros1_package_name': package_name, 'ros2_package_name': package_name, 'ros1_message_name': msg.name, 'ros2_message_name': msg.name})
            mapping_rules[-1]['fields_1_to_2'] = msg.fields_1_to_2
    
    if mapping_rules:
        with open(os.path.join(dst, 'mapping_rules.yaml'), 'w') as f:
            yaml.safe_dump(mapping_rules, f)
        cmake = cmake.replace('<custom_map>', 'install(FILES mapping_rules.yaml DESTINATION share/${PROJECT_NAME})')
        pkg_xml = pkg_xml.replace('<custom_map>', '\n    <ros1_bridge mapping_rules="mapping_rules.yaml"/>')
    else:
        cmake = cmake.replace('<custom_map>', '')
        pkg_xml = pkg_xml.replace('<custom_map>', '')
    
    
    with open(os.path.join(dst, 'CMakeLists.txt'), 'w') as f:
        f.write(cmake)
    with open(os.path.join(dst, 'package.xml'), 'w') as f:
        f.write(pkg_xml)
    
