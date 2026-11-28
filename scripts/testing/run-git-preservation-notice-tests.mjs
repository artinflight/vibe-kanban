import {build} from 'esbuild';
import {spawnSync} from 'node:child_process';
import {mkdir} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
const output=process.env.VK_TEST_OUTPUT;if(!output)throw new Error('Set VK_TEST_OUTPUT to mounted SSD storage');await mkdir(output,{recursive:true});
const require=createRequire(import.meta.url);const outfile=resolve(output,'git-preservation-notice-tests.cjs');
await build({entryPoints:['scripts/testing/git-preservation-notice.test.tsx'],outfile,bundle:true,platform:'node',format:'cjs',jsx:'automatic',tsconfig:'packages/web-core/tsconfig.json',plugins:[{name:'notice-transport-fixture',setup(builder){
 builder.onResolve({filter:/^(react(?:-dom)?(?:\/.*)?|jsdom|@tanstack\/react-query)$/},args=>({path:require.resolve(args.path,{paths:[resolve('packages/web-core'),process.cwd()]}),external:true}));
 builder.onResolve({filter:/^@\/shared\/lib\/(api|localApiTransport)$/},()=>({path:resolve('scripts/testing/git-preservation-notice.fixture.ts')}));
}}]});
const result=spawnSync(process.execPath,['--test',outfile],{stdio:'inherit'});process.exitCode=result.status??1;
