"""Optional cross-runtime check against a local MyOS checkout (JDK 21 required)."""
from pathlib import Path
import argparse
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--myos', type=Path, default=ROOT.parent / 'myos-aws-test')
parser.add_argument('--classpath-file', type=Path, help='Reuse an already built MyOS test runtime classpath')
args = parser.parse_args()
myos = args.myos.resolve()
jdk = Path(os.environ.get('JAVA_HOME', '/Library/Java/JavaVirtualMachines/jdk-21.jdk/Contents/Home'))
with tempfile.TemporaryDirectory(prefix='timeline-compatibility-') as temporary:
    work = Path(temporary)
    classpath_file = args.classpath_file
    if classpath_file is None:
        classpath_file = work / 'classpath.txt'
        init = work / 'classpath.gradle'
        # Pass the output path as a Gradle property; it is never interpolated as code.
        init.write_text('''gradle.projectsEvaluated {
  def core = gradle.rootProject.project(':blue-core-service')
  core.tasks.register('providerCompatibilityClasspath') {
    dependsOn core.tasks.named('classes')
    dependsOn gradle.rootProject.project(':blue-coordination-core').tasks.named('testFixturesClasses')
    dependsOn core.configurations.testRuntimeClasspath
    doLast { new File(gradle.rootProject.property('providerClasspathOutput')).text = core.sourceSets.test.runtimeClasspath.asPath }
  }
}
''')
        subprocess.run(['bash', './gradlew', '-I', str(init),
                        '-PproviderClasspathOutput=' + str(classpath_file),
                        ':blue-core-service:providerCompatibilityClasspath', '--no-daemon'],
                       cwd=myos / 'runtime', env={**os.environ, 'JAVA_HOME': str(jdk)}, check=True)
    classpath = classpath_file.read_text().strip()
    fixture = work / 'fixture.json'
    subprocess.run([sys.executable, str(Path(__file__).with_name('export_fixture.py')), str(fixture)], check=True)
    sources = myos / 'runtime/blue-core-service/src/test/java'
    subprocess.run([str(jdk / 'bin/javac'), '-cp', classpath, '-d', str(work),
                    str(sources / 'blue/core/CompositionPackages.java'),
                    str(sources / 'blue/coordination/AuthoringRuntime.java'),
                    str(Path(__file__).with_name('SignedAccessReplay.java')),
                    str(Path(__file__).with_name('ProviderCompatibility.java'))], check=True)
    result = subprocess.run([str(jdk / 'bin/java'), '-Xmx2g', '-cp', str(work) + os.pathsep + classpath,
                             'blue.core.ProviderCompatibility', str(fixture), str(myos), str(work)])
    sys.exit(result.returncode)
