"""Release contract: Cast needs no user commands or host-side Flatpak dependencies."""
from pathlib import Path
import ast
import unittest

ROOT=Path(__file__).resolve().parent.parent

class CastPlugAndPlay(unittest.TestCase):
    def test_autostart_from_existing_gui_bootstrap(self):
        source=(ROOT/'syn_service_setup.py').read_text('utf-8')
        self.assertIn('syn_cast_autostart.start_once()',source)
        self.assertIn('syn_service_setup.ensure_services_async()',
                      (ROOT/'syn.py').read_text('utf-8'))
        module=(ROOT/'syn_cast_autostart.py').read_text('utf-8')
        self.assertIn('ensure_token()',module)
        self.assertIn('flatpak-spawn',module)
        self.assertIn('syn-cast-bridge.service',module)
        self.assertIn('--command=syn-cast-bridge',module)
        self.assertIn('start_new_session=True',module)
    def test_native_packages_have_dependencies_and_user_unit(self):
        stage=(ROOT/'packaging/stage-native.sh').read_text('utf-8')
        native=(ROOT/'packaging/build-native.sh').read_text('utf-8')
        self.assertIn('syn-cast-bridge.service',stage)
        self.assertIn('default.target.wants/syn-cast-bridge.service',stage)
        self.assertIn('syn_cast_autostart.py',stage)
        for dep in ('python3-chromecast','python3-pychromecast','python-pychromecast'):
            self.assertIn(dep,native)
    def test_flatpak_encodes_without_host_python_or_ffmpeg(self):
        manifest=(ROOT/'com.mrseivane.Syn.yml').read_text('utf-8')
        for token in ('--share=network', 'syn-x264','--enable-libx264',
                      '--enable-gpl','syn_cast_autostart.py',
                      '--find-links=packaging/flatpak-cast-wheels',
                      '/app/bin/syn-cast-bridge','pychromecast==14.0.10'):
            self.assertIn(token,manifest)
        launcher=(ROOT/'syn-cast-bridge').read_text('utf-8')
        self.assertIn('/app/share/syn/vendor',launcher)
        self.assertIn('/app/share/syn/syn_cast_host.py',launcher)
    def test_upstream_cast_pipeline_untouched(self):
        source=(ROOT/'syn_cast_host.py').read_text('utf-8')
        self.assertIn("'-c:v','libx264'",source)
        self.assertIn("'-c:a','aac'",source)
        for path in ('syn_cast_autostart.py','syn_cast_host.py'):
            ast.parse((ROOT/path).read_text('utf-8'),filename=path)

if __name__=='__main__': unittest.main()
