"""Publica el modelo del Colmibot y lo abre en RViz.

Uso:
  ros2 launch robot_description display.launch.py
  ros2 launch robot_description display.launch.py use_meshes:=false   # figuras simples
  ros2 launch robot_description display.launch.py gui:=false rviz:=false
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_share = get_package_share_directory('robot_description')
    default_model = os.path.join(pkg_share, 'urdf', 'colmibot.urdf.xacro')
    default_rviz = os.path.join(pkg_share, 'rviz', 'display.rviz')

    model = LaunchConfiguration('model')
    use_meshes = LaunchConfiguration('use_meshes')
    gui = LaunchConfiguration('gui')
    rviz = LaunchConfiguration('rviz')
    rviz_config = LaunchConfiguration('rviz_config')

    robot_description = ParameterValue(
        Command(['xacro ', model, ' use_meshes:=', use_meshes]),
        value_type=str,
    )

    return LaunchDescription([
        DeclareLaunchArgument('model', default_value=default_model,
                              description='Ruta al archivo xacro del robot'),
        DeclareLaunchArgument('use_meshes', default_value='true',
                              description='true: mallas STL del CAD; false: geometria simplificada'),
        DeclareLaunchArgument('gui', default_value='true',
                              description='Abrir joint_state_publisher_gui para mover las ruedas'),
        DeclareLaunchArgument('rviz', default_value='true',
                              description='Abrir RViz'),
        DeclareLaunchArgument('rviz_config', default_value=default_rviz,
                              description='Archivo de configuracion de RViz'),

        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[{'robot_description': robot_description}],
            output='screen',
        ),
        Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
            condition=IfCondition(gui),
        ),
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            condition=UnlessCondition(gui),
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            arguments=['-d', rviz_config],
            condition=IfCondition(rviz),
            output='screen',
        ),
    ])
