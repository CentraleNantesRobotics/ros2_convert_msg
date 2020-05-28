# ROS message converter

This script converts ROS 1 message-defining packages (`msg` and/or `srv`) into ROS 2 ones.

It also generates, if needed, the mapping rules for `ros1_bridge` to be recompiled. 

## Running the script

ROS 1 workspace should be sourced. The script takes two arguments:

- the path or name of the ROS 1 package, in order to find `msg` and/or `srv` directories
- the path to the ROS 2 workspace where the output ROS 2 package will be created

The ROS 2 workspace can be any path, a new package will be created inside with the exact same name as the ROS 1 package. Names of messages and services are also kept. 

## Change in fields

Field names may be changed to `snake_case` if it was not the case in ROS 1 definitions. 

Field types (mostly `std_msgs/Header` or things related to time) are adapted to ROS 2 interfaces.

## Limitations

As of now only `msg` and `srv` are considered. 
