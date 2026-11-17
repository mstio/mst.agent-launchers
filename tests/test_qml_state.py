"""Exercise the production QML account-state handler with Qt's headless runner."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class CodexMenuStateTest(unittest.TestCase):
    def test_errors_clear_old_commands_and_identical_refresh_keeps_model(self):
        runner = shutil.which("qmltestrunner6") or shutil.which("qmltestrunner")
        if not runner and Path("/usr/lib/qt6/bin/qmltestrunner").is_file():
            runner = "/usr/lib/qt6/bin/qmltestrunner"
        if not runner:
            self.skipTest("Qt Quick Test runner is not installed")
        source = (Path(__file__).resolve().parents[1] / "AgentLaunchers.qml").read_text()
        handler = source[source.index("    function applyCodexState(data) {"):
                         source.index("    function applyStatus(text) {")]
        suite = '''import QtQuick
import QtTest
TestCase {
 id: root
 name: "CodexMenuState"
 property var codexAccounts: []
 property bool codexResumable: false
 property string codexTooltip: ""
''' + handler + '''
 function test_error_discards_stale_launch_commands() {
   codexAccounts = [{id:"old",newCommand:"old-launcher"}]
   codexResumable = true
   applyCodexState({codexAccounts:[],codexError:"Invalid account settings"})
   compare(codexAccounts.length,0)
   compare(codexResumable,false)
   verify(codexTooltip.indexOf("Invalid account settings") >= 0)
 }
 function test_transport_failure_discards_stale_launch_commands() {
   codexAccounts = [{id:"old",newCommand:"old-launcher"}]
   applyCodexState({codexError:"Could not read status"})
   compare(codexAccounts.length,0)
 }
 function test_identical_refresh_keeps_model() {
   codexAccounts = [{id:"one",newCommand:"pinned-launcher"}]
   var previous = codexAccounts
   applyCodexState({codexAccounts:[{id:"one",newCommand:"pinned-launcher"}],codexError:""})
   verify(codexAccounts === previous)
 }
}
'''
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "tst_codex_state.qml").write_text(suite)
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="", QT_QUICK_BACKEND="software")
            result = subprocess.run([runner, "-input", folder], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
