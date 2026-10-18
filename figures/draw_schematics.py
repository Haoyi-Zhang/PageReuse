"""Vector drawing primitives; copied into each independent project generator."""
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle, FancyArrowPatch

plt.rcParams.update({'font.family':'STIXGeneral', 'mathtext.fontset':'stix',
                     'font.size':9, 'pdf.fonttype':42, 'ps.fonttype':42,
                     'text.usetex':False, 'axes.unicode_minus':False})
CM = 1 / 2.54

class Drawing:
    def __init__(self, bounds):
        x0,y0,x1,y1 = bounds
        self.fig = plt.figure(figsize=((x1-x0)*CM,(y1-y0)*CM))
        self.ax = self.fig.add_axes([0,0,1,1], xlim=(x0,x1), ylim=(y0,y1))
        self.ax.set_aspect('equal'); self.ax.axis('off')
        self.nodes = {}
        self.labels = []

    def text(self,x,y,label,size=9,ha='center',va='center'):
        artist=self.ax.text(x,y,label,fontsize=size,ha=ha,va=va,
                            linespacing=1.15,clip_on=False,zorder=4)
        self.labels.append([artist,None])
        return artist

    def box(self,name,x,y,w,h,label,dashed=False,shape='rect',size=9):
        style = {'edgecolor':'black','facecolor':'white','linewidth':.55,
                 'linestyle':(0,(4,3)) if dashed else 'solid', 'zorder':2}
        if shape == 'diamond':
            obj = Polygon([(x-w/2,y),(x,y+h/2),(x+w/2,y),(x,y-h/2)],**style)
        elif shape == 'circle': obj = Circle((x,y),w/2,**style)
        else: obj = Rectangle((x-w/2,y-h/2),w,h,**style)
        self.ax.add_patch(obj); self.text(x,y,label,size)
        self.labels[-1][1]=(x-w/2,y-h/2,x+w/2,y+h/2)
        self.nodes[name] = (x,y,w,h,shape)

    def point(self,name,side):
        x,y,w,h,_ = self.nodes[name]
        return {'n':(x,y+h/2),'s':(x,y-h/2),'e':(x+w/2,y),
                'w':(x-w/2,y),'nw':(x-w/2,y+h/2),
                'ne':(x+w/2,y+h/2),'c':(x,y)}[side]

    def line(self,points,dashed=False):
        xs,ys=zip(*points)
        self.ax.plot(xs,ys,color='black',linewidth=.55,
                     linestyle=(0,(4,3)) if dashed else 'solid',zorder=1)

    def arrow(self,p,q,dashed=False,via=()):
        points=[p,*via,q]
        if via:self.line(points[:-1],dashed)
        self.ax.add_patch(FancyArrowPatch(points[-2],points[-1],
                         arrowstyle='-|>',mutation_scale=7.5,linewidth=.55,
                         color='black',shrinkA=0,shrinkB=0,
                         linestyle=(0,(4,3)) if dashed else 'solid',zorder=1))

    def edge(self,a,b,sa='s',sb='n',**kwargs):
        self.arrow(self.point(a,sa),self.point(b,sb),**kwargs)

    def frame(self,x,y,w,h):
        self.ax.add_patch(Rectangle((x,y),w,h,fill=False,edgecolor='black',
                                   linewidth=.55,linestyle=(0,(4,3)),zorder=0))

    def save(self,out,name):
        # Fixed physical canvas: do not enlarge or rasterize the scientific figure.
        self.fig.canvas.draw()
        renderer=self.fig.canvas.get_renderer()
        x0,x1=self.ax.get_xlim();y0,y1=self.ax.get_ylim()
        for artist,node in self.labels:
            b=artist.get_window_extent(renderer).transformed(self.ax.transData.inverted())
            if b.x0<x0-.02 or b.x1>x1+.02 or b.y0<y0-.02 or b.y1>y1+.02:
                raise ValueError(name+': clipped label '+repr(artist.get_text()))
            if node and (b.x0<node[0]-.02 or b.x1>node[2]+.02 or b.y0<node[1]-.02 or b.y1>node[3]+.02):
                raise ValueError(name+': label exceeds node '+repr(artist.get_text()))
        self.fig.savefig(out/(name+'.pdf'),format='pdf',
                         metadata={'Creator':'Python Matplotlib','Producer':None,
                                   'CreationDate':None,'ModDate':None})
        plt.close(self.fig)
NAMES = ('contract', 'reuse')
def draw_all(out):
    out.mkdir(parents=True, exist_ok=True)
    d = Drawing((-2.02, -4.15, 10.2, .75))
    d.box('trace',0,0,3.25,1.0,'Declared trace\nbindings, lives, masks')
    d.box('prod',5.4,0,3.25,1.0,'Untrusted producer\npartition and potentials')
    d.box('check',5.4,-2,3.25,1.0,'Separate checker\ndirect interval semantics')
    d.box('verdict',0,-2,3.8,1.0,'Contract verdict\nvalidity and minimum cost')
    d.edge('trace','prod','e','w')
    d.edge('prod','check')
    d.text(5.65,-1,'serialized certificate',8.5,ha='left')
    d.arrow((1.625,-.5),(3.775,-1.5))
    d.text(2.7,-.30,'original input',8.5)
    d.edge('check','verdict','w','e')
    d.line([(-1.8,-3.1),(9.8,-3.1)],dashed=True)
    d.text(3.8,-3.65,'Consumed plan → CPU and device byte execution\nSequential boundaries, resident generations, masked loads')
    d.save(out,'contract')
    d = Drawing((-1.35,-4.0,8.8,.92))
    for x,t in ((1.5,0),(3.7,1),(5.9,2)):
        d.text(x,.65,str(t))
        d.line([(x,.35),(x,-3.2)],dashed=True)
    d.text(.65,.65,'step',ha='right')
    for y,left,right,label,points in (
        (0,1.5,3.7,'$a: w=1$',(1.5,)),
        (-.65,1.5,5.9,'$b: w=M$',(3.7,5.9))):
        d.text(.65,y,label,ha='right')
        d.line([(left,y),(right,y)])
        for x in (left,right): d.line([(x,y-.1),(x,y+.1)])
        for x in points:d.ax.plot(x,y,'ko',markersize=3)
    d.text(.65,-1.6,'greedy',ha='right')
    d.box('g01',2.8,-1.6,3.6,.6,'$\\{a,b\\}$')
    d.box('g2',5.6,-1.6,1.6,.6,'$\\{b\\}$')
    d.text(6.65,-1.6,'$2M+3$',ha='left')
    d.text(.65,-2.65,'optimum',ha='right')
    d.box('o0',1.8,-2.65,1.6,.6,'$\\{a\\}$')
    d.box('o12',4.6,-2.65,3.6,.6,'$\\{b\\}$')
    d.text(6.65,-2.65,'$M+3$',ha='left')
    d.line([(1,-3.65),(1.55,-3.65)])
    d.text(1.75,-3.65,'lifetime',ha='left')
    d.ax.plot(3.05,-3.65,'ko',markersize=3)
    d.text(3.3,-3.65,'required occurrence',ha='left')
    d.text(6.5,-3.65,'$\\lambda=1$')
    d.save(out,'reuse')

def main():
    import tempfile
    ap=argparse.ArgumentParser(description='Direct Python vector drawings of the page-reuse contract and running example.')
    ap.add_argument('--output',type=Path,default=Path(__file__).resolve().parent)
    ap.add_argument('--check',action='store_true')
    args=ap.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp);draw_all(out)
            for name in NAMES:
                if not (args.output/(name+'.pdf')).is_file() or (args.output/(name+'.pdf')).read_bytes()!=(out/(name+'.pdf')).read_bytes():
                    raise SystemExit('Missing/stale schematic: '+name)
        print('Both page-reuse schematics reproduce byte-for-byte.')
    else:draw_all(args.output)
if __name__=='__main__':main()
