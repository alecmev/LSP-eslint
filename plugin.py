import os
import posixpath
import re
import sublime
import webbrowser

from LSP.plugin.core.url import uri_to_filename
from lsp_utils import NpmClientHandler


def plugin_loaded():
    LspEslintPlugin.setup()


def plugin_unloaded():
    LspEslintPlugin.cleanup()


class LspEslintPlugin(NpmClientHandler):
    package_name = __package__
    server_directory = 'language-server'
    server_binary_path = os.path.join(server_directory, 'out', 'eslintServer.js')

    def on_ready(self, api) -> None:
        api.on_notification('eslint/status', self.handle_status)
        api.on_request('eslint/openDoc', self.handle_open_doc)

    def handle_status(self, params) -> None:
        pass

    def handle_open_doc(self, params, respond) -> None:
        webbrowser.open(params['url'])
        respond({})

    def on_workspace_configuration(self, params, configuration) -> None:
        session = self.weaksession()
        if session:
            scope_uri = params.get('scopeUri')
            if scope_uri:
                workspace_folder = None
                for folder in session.get_workspace_folders():
                    if folder.includes_uri(scope_uri):
                        workspace_folder = folder
                        break
                if workspace_folder:
                    configuration['workspaceFolder'] = workspace_folder.to_lsp()
                self.resolve_working_directory(configuration, scope_uri, workspace_folder)

    def resolve_working_directory(self, configuration, scope_uri, workspace_folder) -> None:
        working_directories = configuration.get('workingDirectories', None)
        if isinstance(working_directories, list):
            working_directory = None
            workspace_folder_path = workspace_folder.path if workspace_folder else None
            for entry in working_directories:
                directory = None
                no_cwd = False
                if isinstance(entry, str):
                    directory = entry
                elif self.is_working_directory_item(entry, 'directory'):
                    directory = entry.directory
                    if isinstance(entry.get('!cwd', None), bool):
                        no_cwd = entry['!cwd']
                elif self.is_working_directory_item(entry, 'pattern'):
                    print('LSP-eslint: workingDirectories configuration that uses "pattern" is not supported')
                    continue
                elif self.is_mode_item(entry):
                    working_directory = entry
                    continue

                directory_value = None
                if directory:
                    file_path = uri_to_filename(scope_uri)
                    if directory:
                        directory = self.to_os_path(directory)
                        if not os.path.isabs(directory) and workspace_folder_path:
                            # Trailing '' will add trailing slash if missing.
                            directory = os.path.join(workspace_folder_path, directory, '')
                        if file_path.startswith(directory):
                            directory_value = directory

                if directory_value:
                    if not working_directory or self.is_mode_item(working_directory):
                        working_directory = {'directory': directory_value, '!cwd': no_cwd}
                    else:
                        if len(working_directory['directory']) < len(directory_value):
                            working_directory['directory'] = directory_value
                            working_directory['!cwd'] = no_cwd
            configuration['workingDirectory'] = working_directory
            configuration.pop('workingDirectories', None)

    def is_working_directory_item(self, item, configuration_key) -> bool:
        if isinstance(item, dict):
            value = item.get(configuration_key, None)
            not_cwd = item.get('!cwd', None)
            return isinstance(value, str) and (isinstance(not_cwd, bool) or not_cwd is None)
        return False

    def is_mode_item(self, item) -> bool:
        if isinstance(item, dict):
            mode = item.get('mode', None)
            return isinstance(mode, str) and mode in ('auto', 'location')
        return False

    def to_os_path(self, path) -> str:
        if sublime.platform == 'windows':
            path = re.sub(r'^\/(\w)\/', r'\1:\\', path)
        return os.path.normpath(path)
