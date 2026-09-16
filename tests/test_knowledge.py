from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import knowledge as k


class KnowledgeWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        (self.vault / 'AGENTS.md').write_text('Test rules')
        (self.vault / '00 首页.md').write_text('# Test home')
        self.local_patch = patch.object(k, 'LOCAL', self.root / 'runtime')
        self.local_patch.start()
        self.addCleanup(self.local_patch.stop)
        source = self.root / 'input.txt'
        source.write_bytes('虚构试用记录：检索中文知识。\r\n'.encode())
        self.source_bytes = source.read_bytes()
        args = SimpleNamespace(source=source, id='source-demo', title='虚构示例',
                               origin='fictional-fixture', sensitivity='private',
                               kind='observation', as_of=dt.date(2030, 1, 1))
        self.ingest_args = args
        k.ingest(args, self.vault)

    def content(self, title='示例知识', sensitivity='private'):
        return k.header('knowledge', 'knowledge-demo', title, sensitivity,
                        ['[[80 来源/source-demo/record]]'], status='draft') + '待验证：示例知识。\n'

    def plan(self, content=None, before=None, name='70 知识/示例.md'):
        p = self.root / 'plan.json'
        p.write_text(json.dumps({'version': 1, 'vault': str(self.vault), 'summary': '虚构测试',
                     'writes': [{'path': name, 'before_sha256': before, 'content': content or self.content()}]}, ensure_ascii=False))
        return p

    def test_source_is_preserved_and_immutable(self):
        self.assertEqual((self.vault / '80 来源/source-demo/source.txt').read_bytes(), self.source_bytes)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            k.ingest(self.ingest_args, self.vault)

    def test_preview_is_read_only_then_apply_has_index_log_checkpoint(self):
        p = self.plan()
        before_files = sorted(str(f) for f in self.vault.rglob('*'))
        with contextlib.redirect_stdout(io.StringIO()):
            code = k.main(['--vault', str(self.vault), 'preview', str(p)])
        self.assertEqual(code, 0)
        self.assertEqual(before_files, sorted(str(f) for f in self.vault.rglob('*')))
        result = k.apply_plan(p, self.vault, k.digest(p.read_bytes()), 'fixture approval', k.vault_digest(self.vault))
        self.assertIn('70 知识/示例.md', result['files'])
        self.assertIn('[[70 知识/示例|示例知识]]', (self.vault / k.INDEX).read_text())
        self.assertIn('manifest.json', (self.vault / k.LOG).read_text())
        manifest = json.loads((Path(result['checkpoint']) / 'manifest.json').read_text())
        self.assertEqual(manifest['status'], 'applied')
        self.assertEqual(manifest['approval_ref'], 'fixture approval')
        self.assertFalse((self.vault / '.myself-write.lock').exists())

    def test_changed_plan_or_stale_target_rejected(self):
        p = self.plan()
        with self.assertRaisesRegex(ValueError, 'changed after preview'):
            k.apply_plan(p, self.vault, 'old-hash', 'fixture', k.vault_digest(self.vault))
        target = self.vault / '70 知识/示例.md'
        target.parent.mkdir()
        target.write_text(self.content())
        with self.assertRaisesRegex(ValueError, 'stale target'):
            k.load_plan(p, self.vault)

    def test_raw_personal_state_reserved_and_escape_paths_rejected(self):
        for name in ['../out.md', '01 基础/当前状态.md', k.INDEX, k.LOG,
                     '70 知识/../out.md', '70 知识/.private/out.md']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                k.load_plan(self.plan(name=name), self.vault)

    def test_symlink_and_public_private_crossing_rejected(self):
        outside = self.root / 'elsewhere'
        outside.mkdir()
        (self.vault / '70 知识').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            k.load_plan(self.plan(), self.vault)
        (self.vault / '70 知识').unlink()
        with self.assertRaisesRegex(ValueError, 'public sources'):
            k.load_plan(self.plan(self.content(sensitivity='public')), self.vault)

    def test_source_provenance_must_resolve(self):
        text = self.content().replace('source-demo/record', 'missing-source/record')
        with self.assertRaisesRegex(ValueError, 'unresolved link'):
            k.load_plan(self.plan(text), self.vault)

    def test_writer_rolls_back_on_write_failure(self):
        p = self.plan()
        original_write = k.atomic_write
        def fail_index(path, data):
            if path == self.vault / k.INDEX:
                raise OSError('simulated failure')
            return original_write(path, data)
        with patch.object(k, 'atomic_write', fail_index), self.assertRaises(OSError):
            k.apply_plan(p, self.vault, k.digest(p.read_bytes()), 'fixture', k.vault_digest(self.vault))
        self.assertFalse((self.vault / '70 知识/示例.md').exists())
        self.assertFalse((self.vault / k.LOG).exists())
        self.assertEqual((self.vault / '80 来源/source-demo/source.txt').read_bytes(), self.source_bytes)

    def test_lock_prevents_second_writer(self):
        p = self.plan()
        with k.writer_lock(self.vault), self.assertRaises(FileExistsError):
            k.apply_plan(p, self.vault, k.digest(p.read_bytes()), 'fixture', k.vault_digest(self.vault))

    def test_same_page_source_anchor_is_not_provenance(self):
        text = self.content().replace('80 来源/source-demo/record', '#依据')
        with self.assertRaisesRegex(ValueError, 'same-page anchors'):
            k.load_plan(self.plan(text), self.vault)

    def test_ingest_id_cannot_shadow_existing_knowledge(self):
        (self.vault / 'existing.md').write_text(k.header('knowledge', 'source-another', 'Existing'))
        self.ingest_args.id = 'source-another'
        with self.assertRaisesRegex(ValueError, 'id already exists'):
            k.ingest(self.ingest_args, self.vault)

    def test_source_change_after_preview_blocks_apply(self):
        p = self.plan()
        snapshot = k.vault_digest(self.vault)
        (self.vault / '80 来源/source-demo/source.txt').write_text('changed externally')
        with self.assertRaisesRegex(ValueError, 'vault changed'):
            k.apply_plan(p, self.vault, k.digest(p.read_bytes()), 'fixture', snapshot)

    def test_rollback_preserves_existing_index_and_page(self):
        target = self.vault / '70 知识/示例.md'
        target.parent.mkdir()
        target.write_text(self.content())
        index = self.vault / k.INDEX
        index.write_text('User original index\n<!-- myself:index:start -->\nold\n<!-- myself:index:end -->\n')
        old_index = index.read_text()
        original = target.read_bytes()
        p = self.plan(self.content('Updated'), k.digest(original))
        atomic = k.atomic_write
        def fail_index(path, data):
            if path == index:
                raise OSError('simulated persistent index failure')
            return atomic(path, data)
        with patch.object(k, 'atomic_write', fail_index), self.assertRaises(OSError):
            k.apply_plan(p, self.vault, k.digest(p.read_bytes()), 'fixture', k.vault_digest(self.vault))
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(index.read_text(), old_index)

    def test_preview_includes_derived_diff_and_preserves_index_notes(self):
        p = self.plan()
        index = self.vault / k.INDEX
        index.parent.mkdir()
        index.write_text('MY NOTE\n<!-- myself:index:start -->\nold\n<!-- myself:index:end -->\nKEEP FOOTER\n')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(k.main(['--vault', str(self.vault), 'preview', str(p)]), 0)
        self.assertIn('+++ ' + k.INDEX, out.getvalue())
        self.assertIn('+++ ' + k.LOG, out.getvalue())
        k.apply_plan(p, self.vault, k.digest(p.read_bytes()), 'fixture', k.vault_digest(self.vault))
        self.assertTrue(index.read_text().startswith('MY NOTE'))
        self.assertTrue(index.read_text().endswith('KEEP FOOTER\n'))

    def test_unmanaged_index_is_not_overwritten(self):
        p = self.plan()
        index = self.vault / k.INDEX
        index.parent.mkdir()
        index.write_text('Existing user index')
        with self.assertRaisesRegex(ValueError, 'not tool-managed'):
            k.apply_plan(p, self.vault, k.digest(p.read_bytes()), 'fixture', k.vault_digest(self.vault))
        self.assertEqual(index.read_text(), 'Existing user index')
        self.assertFalse((self.vault / '70 知识/示例.md').exists())

    def test_first_page_can_link_same_batch_index_and_log(self):
        text = self.content() + '\n[[70 知识/index]]\n[[07 项目/Myself/演进记录]]\n'
        p = self.plan(text)
        k.load_plan(p, self.vault)
        k.apply_plan(p, self.vault, k.digest(p.read_bytes()), 'fixture', k.vault_digest(self.vault))
        self.assertTrue((self.vault / k.INDEX).is_file())
        self.assertTrue((self.vault / k.LOG).is_file())
        text = self.content().replace('80 来源/source-demo/record', '70 知识/index')
        with self.assertRaisesRegex(ValueError, 'navigation cannot'):
            k.load_plan(self.plan(text, k.digest((self.vault / '70 知识/示例.md').read_bytes())), self.vault)

    def test_existing_page_id_cannot_change(self):
        target = self.vault / '70 知识/示例.md'
        target.parent.mkdir()
        target.write_text(self.content())
        p = self.plan(self.content().replace('knowledge-demo', 'knowledge-other'), k.digest(target.read_bytes()))
        with self.assertRaisesRegex(ValueError, 'id cannot be changed'):
            k.load_plan(p, self.vault)


if __name__ == '__main__':
    unittest.main()
