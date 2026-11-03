"""Bounded request/response client for the native Praetor probe-worker."""
import os,select,subprocess,time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import moon
class ProbeWorker:
    def __init__(self,binary,folder,deadline):
        self.deadline=deadline;self.buffer=b'';clock=time.monotonic();tick=time.process_time()
        self.errors=open(Path(folder)/f'worker-{time.time_ns()}.err','wb')
        self.proc=subprocess.Popen([str(binary),'probe-worker','1439','2310','256','25','10000001','10000000'],cwd=folder,env=dict(os.environ,HUNTER_PATTERNS='1'),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.errors)
        self.errors.close()
        setup=0
        try:
            while True:
                line=self.line()
                if line.startswith('@setup\t'):setup=int(line.split('\t')[1])/1e9
                if line=='worker ready':break
        except BaseException:self.close();raise
        self.setup_cpu=setup+time.process_time()-tick;self.setup_wall=time.monotonic()-clock
    def line(self):
        while b'\n' not in self.buffer:
            left=self.deadline-time.monotonic()
            if left<=0:raise TimeoutError('probe worker deadline')
            if not select.select([self.proc.stdout],[],[],left)[0]:raise TimeoutError('probe worker deadline')
            block=os.read(self.proc.stdout.fileno(),65536)
            if not block:raise RuntimeError(f'probe worker exited {self.proc.poll()}')
            self.buffer+=block
        line,self.buffer=self.buffer.split(b'\n',1);return line.decode()
    def probe(self,start,count,depth,selected=None):
        selected=selected or [];clock=time.monotonic();tick=time.process_time()
        command=' '.join(map(str,[start,count,depth,len(selected),*selected]))+'\n'
        self.proc.stdin.write(command.encode());self.proc.stdin.flush();lines=[];cpu=None
        while True:
            line=self.line();lines.append(line)
            if line.startswith('@cost\t'):cpu=int(line.split('\t')[1])/1e9
            if line.startswith('probe complete'):break
        text='\n'.join(lines)+'\n';rows=moon.parse(text)
        if cpu is None:raise RuntimeError('missing worker timing')
        return rows,cpu+time.process_time()-tick,time.monotonic()-clock,text
    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
        self.proc.stdin.close();self.proc.stdout.close()
