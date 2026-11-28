#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安装器入口与布局行生成：区分版本目录模式与非版本目录模式。

版本目录模式（同时给出 payload_dir 与 updater）由独立启动器拉起 versions/<版本>/，
不再把根目录 onefile 主 EXE 打进安装器，并清理升级前旧版遗留的根目录主 EXE。

@author Author
"""
from __future__ import annotations

from pathlib import Path


def is_version_dir_mode(payload_dir: "Path | None", updater: "Path | None") -> bool:
    """判定是否走版本目录模式：完整 payload 与独立启动器两者缺一不可。"""
    return payload_dir is not None and updater is not None


def icon_lines(payload_dir: "Path | None", updater: "Path | None") -> tuple[str, str]:
    """有完整版本 payload 与启动器时让快捷方式走启动器，否则保留旧的 onefile 入口。"""
    if is_version_dir_mode(payload_dir, updater):
        parameters = ('Parameters: "--start --version-root ""{app}\\versions"" '
                      '--current-file ""{app}\\current.json"""')
        main = ('Name: "{group}\\{#MyAppName}"; Filename: "{app}\\update-launcher.exe"; '
                + parameters)
        desktop = ('Name: "{autodesktop}\\{#MyAppName}"; '
                   'Filename: "{app}\\update-launcher.exe"; ' + parameters +
                   '; Tasks: desktopicon')
        return main, desktop
    return ('Name: "{group}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"',
            'Name: "{autodesktop}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"; '
            'Tasks: desktopicon')


def root_exe_line(exe: Path, exe_name: str,
                  payload_dir: "Path | None", updater: "Path | None") -> str:
    """非版本目录模式保留根目录主 EXE；版本目录模式不再打入这份重复 EXE。"""
    if is_version_dir_mode(payload_dir, updater):
        return ""
    return ('Source: "%s"; DestDir: "{app}"; DestName: "%s"; Flags: ignoreversion\n'
            % (Path(exe), exe_name))


def uninstall_icon_value(payload_dir: "Path | None", updater: "Path | None") -> str:
    """控制面板卸载条目图标：版本目录模式改指启动器，其余指根目录主 EXE。"""
    if is_version_dir_mode(payload_dir, updater):
        return "{app}\\update-launcher.exe"
    return "{app}\\{#MyAppExeName}"


def install_delete_section(payload_dir: "Path | None", updater: "Path | None") -> str:
    """版本目录模式安装前删除旧版遗留的根目录主 EXE，防止旧入口一直启动旧版本。"""
    if is_version_dir_mode(payload_dir, updater):
        return '[InstallDelete]\nType: files; Name: "{app}\\{#MyAppExeName}"\n\n'
    return ""
