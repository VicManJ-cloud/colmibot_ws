"""Carga el modelo y lo abre en RViz con los sliders de articulaciones."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg = get_package_share_directory('robot_description')
    modelo = os.path.join(pkg, 'urdf', 'colmibot.urdf.xacro')
    rviz_cfg = os.path.join(pkg, 'rviz', 'colmibot.rviz')

    # xacro se procesa al vuelo: no hay que regenerar un .urdf a mano.
    robot_description = ParameterValue(
        Command(['xacro ', LaunchConfiguration('modelo')]),
        value_type=str,
    )

    return LaunchDescription([
        DeclareLaunchArgument('modelo', default_value=modelo),
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[{'robot_description': robot_description}],
        ),
        Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            arguments=['-d', rviz_cfg],
        ),
    ])
