"""Prepare only against an exact adapter hash; never install or restart."""
import argparse
import ast
import hashlib
from pathlib import Path
import shutil


def patched(source):
    if 'import launcher' in source:
        raise ValueError('Launcher already integrated; reconcile the baseline')
    for marker in ('"connector_queued_for_capacity"', 'require_issue_context', 'dispatch_start(local_start,args)',
                   'observe(name,args,local_followup(args)', 'stop_control.HANDLERS', 'sidechat_connector.TOOLS'):
        if marker not in source:
            raise ValueError('Required owner/capacity/security integration missing')
    replacements = [
        ('import stop_control\n', 'import stop_control\nimport launcher\n'),
        ('def local_start(args):', 'def codex_local_start(args):'),
        ('def local_followup(args):', 'def codex_local_followup(args):'),
        ('def recommend_config(config):', 'def codex_recommend_config(config):'),
        ('    if not session.get("success") or session["data"].get("executor")!="CODEX": raise ValueError("Cannot resolve CODEX session")',
         '    if not session.get("success") or session["data"].get("executor") not in ("CODEX", "CLAUDE_CODE"): raise ValueError("Unsupported session executor; no request sent")\n'
         '    if session["data"]["executor"] == "CLAUDE_CODE":\n'
         '        if session["data"].get("id") != sid: raise ValueError("Session identity mismatch")\n'
         '        return launcher.resolve_claude(sys.modules[__name__], sid, session["data"])'),
        ('    return recommend_config(config)\n\ndef post_fixed',
         '    if config.get("executor") != session["data"]["executor"]: raise ValueError("Saved draft executor mismatch; no request sent")\n'
         '    return recommend_config(config)\n\ndef post_fixed'),
        ('"enum":["CODEX"]', '"enum":["CODEX","CLAUDE_CODE"]'),
        ('Recommend-only routing is mandatory: records recommendations while retaining the selected execution model/effort. ', 'CODEX uses Recommend-only routing; Claude retains the selected model/effort without a routing recommendation. '),
        ('Create and start a CODEX workspace', 'Create and start an explicitly selected CODEX or CLAUDE_CODE workspace'),
        (' + sidechat_connector.TOOLS', ' + launcher.TOOLS + sidechat_connector.TOOLS'),
        ('            if name in stop_control.HANDLERS:',
         '            if name in launcher.HANDLERS:\n'
         '                return {"jsonrpc":"2.0","id":msg["id"],"result":launcher.HANDLERS[name](sys.modules[__name__],args)}\n'
         '            if name in stop_control.HANDLERS:'),
        ('                if name == "list_projects":',
         '                if name == "run_session_prompt":\n'
         '                    tool["inputSchema"] = {"type":"object", "properties": {"session_id":launcher.UUID, "prompt":{"type":"string", "minLength":1, "maxLength":60000}, **{k:{"type":"string"} for k in launcher.SELECTION}}, "required":["session_id","prompt"], "additionalProperties":False}\n'
         '                if name == "start_workspace":\n'
         '                    tool["inputSchema"] = launcher.workspace_schema()\n'
         '                    tool["description"] += " Claude requires an explicit supported model: opus, opus[1m], sonnet or haiku. Unsupported effort is rejected. Claude routing recommendations and provider quota are unavailable; missing quota means unknown, never extra-usage authorization."\n'
         '                if name == "list_projects":'),
    ]
    for before, after in replacements:
        if source.count(before) != 1:
            raise ValueError('Adapter changed; reconcile launcher integration anchors')
        source = source.replace(before, after)
    source += '''\n# Keep authenticated dispatch/observation wrappers and the CODEX lane intact.
def local_start(args):
    return launcher.start(sys.modules[__name__], args)

def local_followup(args):
    return launcher.followup(sys.modules[__name__], args)

def recommend_config(config):
    return launcher.recommend(sys.modules[__name__], config)

def handoff_result(value):
    output = result(value)
    output["isError"] = value["status"] != "started"
    if value["status"] == "started":
        from dispatch_notes import observe, current_caller
        note = observe("run_session_prompt", {"session_id":value["target_session_id"]},
                       result({"execution_id":value["target_execution_id"]}), caller=current_caller())
        output["content"].extend(note.get("content", [])[1:])
    return output
'''
    # Wrapper definitions must execute before a stdio main loop can begin.
    anchor = '\nif __name__ == "__main__": main()'
    if anchor in source:
        source = source.replace(anchor, '') + anchor + '\n'
    else:
        # Accept the conventional two-line entrypoint, but never guess its placement.
        tree = ast.parse(source)
        guards = [n for n in tree.body if isinstance(n, ast.If) and '__name__' in ast.unparse(n.test)]
        if len(guards) != 1:
            raise ValueError('Review adapter entrypoint before preparation')
        lines = source.splitlines(keepends=True)
        guard = guards[0]
        entry = ''.join(lines[guard.lineno - 1:guard.end_lineno])
        source = ''.join(lines[:guard.lineno - 1] + lines[guard.end_lineno:]) + '\n' + entry
    compile(source, '<prepared-launcher-adapter>', 'exec')
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.adapter.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.expected_sha256:
        parser.error('Adapter baseline changed; reconcile before preparation')
    candidate = patched(raw.decode())
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'adapter.py').write_text(candidate)
    shutil.copyfile(Path(__file__).with_name('launcher.py'), args.output / 'launcher.py')
    print('Prepared launcher candidate only; no live files, settings or services changed.')


if __name__ == '__main__':
    main()
