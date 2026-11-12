#!/usr/bin/env python3
"""Compile exact policy functions offline, without Cargo, dependencies or providers.

Serialization derives alone are omitted from lifted production data types. This
checks policy behavior and unchanged launch fences, NOT full backend/native E2E.
"""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=pathlib.Path, required=True)
p.add_argument('--baseline', default='bc3b89deef1203dcf8851c0e294a58c8fbeca1de')
a = p.parse_args()
subprocess.run(['mountpoint', '-q', '/mnt/vk-storage'], check=True)
if not a.output.resolve().is_relative_to('/mnt/vk-storage'):
    raise SystemExit('Output must be on mounted secondary storage')
a.output.mkdir(parents=True, exist_ok=True)
routing_path = ROOT / 'crates/executors/src/routing.rs'
delegation_path = ROOT / 'crates/executors/src/routing_delegation.rs'
wire_path = ROOT / 'crates/executors/src/executors/codex/delegation.rs'
test_path = ROOT / 'crates/executors/src/routing_delegation_advisory_tests.rs'
routing, delegation, wire = [p.read_text() for p in (routing_path, delegation_path, wire_path)]

def block(source, marker):
    start = source.index(marker)
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    # Used only for these simple data declarations/validation methods. Fail the
    # compile if source changes; never replace production behavior with a copy.
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

def datatype(source, kind, name):
    text = re.sub(r'#\[[^\]]*\]\s*', '', block(source, f'pub {kind} {name}'))
    derive = 'Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord' if kind == 'enum' else 'Debug, Clone'
    return f'#[derive({derive})]\n' + text

types = '\n'.join(datatype(routing, kind, name) for kind, name in [
    ('enum', 'RoutingMode'), ('enum', 'CapabilityFloor'), ('struct', 'RoutingPolicy'),
    ('enum', 'QualificationStatus'), ('struct', 'Qualification'),
    ('struct', 'ModelPolicy'), ('struct', 'Availability'), ('struct', 'ModelAvailability')])
availability = routing[routing.index('impl Availability {'):routing.index('pub fn model_policies()')]
selector = routing[routing.index('pub fn choose_assessed('):routing.index('pub fn account_fingerprint(')]
policy = delegation[delegation.index('fn escalation_requires_consent('):delegation.index('\n#[cfg(test)]')]
assignment = datatype(delegation, 'struct', 'Assignment')
validation = block(delegation, 'pub fn validate(')
overlap = block(delegation, 'pub fn overlaps(')
harness = a.output / 'policy.rs'
harness.write_text('#![allow(dead_code)]\nmod routing {\n' + types + availability + selector + '\n}\n'
    + 'use routing::{CapabilityFloor, RoutingMode, RoutingPolicy};\nuse std::path::{Path,Component};\n'
    + assignment + '\nimpl Assignment {\n' + validation + overlap + '\n}\n' + policy
    + '\n#[path=' + json.dumps(str(test_path)) + '] mod tests;\n')
# Exercise the actual model/effort branch in launch_choice. Only its I/O sources
# (catalog and clock) and protocol parameter carrier are fixtures. No RPC/worker.
selection = wire[wire.index('        let (model, effort) = if self.policy.mode'):wire.index('        let brief_floor =')]
legacy = subprocess.check_output(['git', 'show', f'{a.baseline}:{delegation_path.relative_to(ROOT)}'], cwd=ROOT, text=True)
legacy = legacy[legacy.index('pub fn actual_pair_qualified('):legacy.index('\n#[cfg(test)]')]
with harness.open('a') as out:
    out.write(datatype(delegation, 'struct', 'ChildChoice') + '\ntype SemanticTrace = ();\n')
    out.write("""
mod chrono { pub struct Utc; impl Utc { pub fn now() -> Self { Self } pub fn timestamp(&self) -> i64 { 100 } } }
mod launch_fixture {
    use super::*;
    use std::collections::HashMap;
    struct Value(String); impl Value { fn as_str(&self) -> Option<&str> { Some(&self.0) } }
    struct Params { model: Option<String>, config: Option<HashMap<String, Value>> }
    struct Control { policy: RoutingPolicy }
    impl Control {
        fn select(&self, params: Params, choice: &ChildChoice) -> Result<(String,String),String> {
""" + selection + """
            Ok((model, effort))
        }
    }
    fn params() -> Params { Params { model: Some("gpt-6.1-sol".into()), config: Some(HashMap::from([("model_reasoning_effort".into(),Value("xhigh".into()))])) } }
    fn advice() -> ChildChoice { ChildChoice { envelope:"protected".into(), floor:CapabilityFloor::Frontier, model:"gpt-6-astra".into(), effort:"high".into(), source:"protected task assessment".into(), semantic:None, escalated:false } }
    #[test] fn real_launch_branch_preserves_selected_pair_and_stronger_advice() {
        let (policy, models, availability) = tests::fixture(); routing::set_sources(models,availability);
        let choice=advice();
        assert!(!legacy::actual_pair_qualified(&choice,"gpt-6.1-sol","xhigh",&policy).unwrap(), "original veto reproduced");
        assert_eq!(Control{policy}.select(params(),&choice).unwrap(),("gpt-6.1-sol".into(),"xhigh".into()));
        assert_eq!(choice.model,"gpt-6-astra"); assert_eq!(choice.source,"protected task assessment");
    }
    #[test] fn real_launch_branch_still_rejects_explicit_exclusion() {
        let (mut policy,models,availability)=tests::fixture(); routing::set_sources(models,availability);
        policy.denied_models.push("gpt-6.1-sol".into());
        assert!(Control{policy}.select(params(),&advice()).unwrap_err().contains("excluded"));
    }
    #[test] fn real_auto_launch_branch_keeps_its_qualified_choice() {
        let (mut policy,models,availability)=tests::fixture(); routing::set_sources(models,availability); policy.mode=RoutingMode::Auto;
        assert_eq!(Control{policy}.select(params(),&advice()).unwrap(),("gpt-6-astra".into(),"high".into()));
    }
}
mod legacy { use super::*;
""" + legacy + '\n}\n')
# The exact production policy wrapper delegates to the behavior-tested function.
text = harness.read_text().replace('mod routing {\n', """mod routing {
    thread_local! { static SOURCES: std::cell::RefCell<Option<(Vec<ModelPolicy>,Availability)>> = const { std::cell::RefCell::new(None) }; }
    pub fn set_sources(m: Vec<ModelPolicy>, a: Availability) { SOURCES.set(Some((m,a))); }
    pub fn model_policies() -> Result<Vec<ModelPolicy>,String> { Ok(SOURCES.with_borrow(|s| s.as_ref().unwrap().0.clone())) }
    pub fn load_availability() -> Result<Availability,String> { Ok(SOURCES.with_borrow(|s| s.as_ref().unwrap().1.clone())) }
""")
text += '\nmod routing_delegation { pub use super::advisory_pair; }\n'
harness.write_text(text)
worker = a.output / 'policy-tests'
subprocess.run(['rustc', '--edition=2024', '--test', str(harness), '-C', 'debuginfo=0', '-o', str(worker)], check=True)
subprocess.run([str(worker), '--test-threads=1'], cwd=ROOT, check=True)

# Bind the behavior-tested advisory gate to the real transport, while verifying
# the surrounding launch/permission/ownership code has no changes in this patch.
old = subprocess.check_output(['git', 'show', f'{a.baseline}:{wire_path.relative_to(ROOT)}'], cwd=ROOT, text=True)
launch_marker = '    /// Transport boundary isolated from assessment'
assert wire[:wire.index('    async fn launch(')] == old[:old.index('    async fn launch(')]
transport = wire[wire.index('        params.model = Some(model.clone());'):wire.index('\n    async fn bind(')]
transport = transport.replace('assignment.brief(brief_floor)', 'assignment.brief(crate::routing_delegation::hard_floor(&self.policy,&self.parent))')
assert transport == old[old.index('        params.model = Some(model.clone());'):old.index('\n    async fn bind(')]
assert wire[wire.index('\n    async fn bind('):] == old[old.index('\n    async fn bind('):]
assert 'actual_pair_qualified' not in wire
selection = wire[wire.index(launch_marker):wire.index('        params.model = Some(model.clone());')]
assert 'if self.policy.mode == RoutingMode::Auto' in selection
assert '(choice.model.clone(), choice.effort.clone())' in selection
assert 'crate::routing_delegation::advisory_pair(' in selection
assert 'self.policy' in selection and 'load_availability()?' in selection
print('PASS: production call site and three unchanged launch/fence regions (static checks, not native acceptance)')
receipt = {'kind': 'source-bound-offline-policy', 'providerCalls': 0, 'nativeAcceptance': False,
    'baseline': a.baseline, 'files': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [routing_path, delegation_path, wire_path, test_path, pathlib.Path(__file__)]}}
(a.output / 'source-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
