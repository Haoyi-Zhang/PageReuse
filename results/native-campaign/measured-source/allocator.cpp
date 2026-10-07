// Original MIT-licensed C++17 CPU executor. See ../LICENSE.
// No network, threads, device access, external allocator, or numerical attention.
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <limits>
#include <memory>
#include <stdexcept>
#include <vector>

#ifdef _WIN32
#define EXPORT extern "C" __declspec(dllexport)
#else
#define EXPORT extern "C" __attribute__((visibility("default")))
#endif
struct Page { int32_t slot, generation, content, group, first, last, base, length, width; };
struct Epoch { int32_t start, end, offset, count; };
struct Descriptor { int32_t page, slot, generation, content, width, group, offset, length, start, end; };
struct Counts { int64_t loads, bytes, publications, copies; uint64_t sink; };
using Observe = void (*)(int32_t,int32_t,int32_t,int32_t,int32_t,int32_t,int32_t,int32_t,int32_t,int32_t,int32_t,uint64_t);
static void need(bool ok,const char* msg) { if(!ok)throw std::runtime_error(msg); }
static void error(char* out,int capacity,const char* msg) { if(out&&capacity>0){std::strncpy(out,msg,static_cast<size_t>(capacity)-1);out[capacity-1]=0;} }
struct Context {
    int B,T,P,bytes;
    std::vector<Page> pages;
    std::vector<int32_t> frontiers;
    std::vector<uint8_t> mandatory;
    std::vector<uint32_t> scratch;
    std::vector<Descriptor> published;
    int resident[256], generations[256], initialized[256];
    uint8_t* raw=nullptr;
    uint8_t* data=nullptr;
    ~Context(){std::free(raw);}
    void reset(){std::fill_n(resident,256,-1);std::fill_n(generations,256,0);std::fill_n(initialized,256,0);published.clear();}
    static uint32_t payload(const Page& p,int i){uint64_t v=uint64_t(p.content)*131+uint64_t(p.generation)*17+uint64_t(p.group)*7+uint64_t(i)*29;return uint32_t(v&(p.width==2?65535:255));}
    int cap(int t,const Page& p)const{return int(std::min<int64_t>(p.length,std::max<int64_t>(0,int64_t(frontiers[t])-p.base+1)));}
    void guards()const{for(int i=0;i<32;++i)need(raw[i]==0xD3&&data[bytes+i]==0xD3,"arena canary");}
    void boundary(int t,Observe obs){
        for(int p=0;p<P;++p){auto& m=pages[p];if(m.last==t-1){need(resident[m.slot]==p,"retirement occupant");resident[m.slot]=-1;initialized[m.slot]=0;
            if(obs)obs(0,t,p,m.slot,m.generation,-1,m.width,m.slot*2*B,0,-1,-1,0);}}
        for(int p=0;p<P;++p){auto& m=pages[p];if(m.first==t){need(resident[m.slot]==-1&&generations[m.slot]<m.generation,"activation order");int off=m.slot*2*B;
            std::memset(data+off,0xA5,2*B);
            for(int i=0;i<m.length;++i){uint32_t v=payload(m,i);data[off+i*m.width]=uint8_t(v);if(m.width==2)data[off+i*2+1]=uint8_t(v>>8);}
            initialized[m.slot]=m.length;generations[m.slot]=m.generation;resident[m.slot]=p;
            if(obs)obs(1,t,p,m.slot,m.generation,-1,m.width,off,m.content,-1,-1,reinterpret_cast<uintptr_t>(data+off));}}
    }
    void validate(const Descriptor& d,int t)const{
        need(d.page>=0&&d.page<P&&d.slot>=0&&d.slot<256,"descriptor indices");auto& m=pages[d.page];
        need(d.start<=t&&t<=d.end,"lease step");need(resident[d.slot]==d.page&&generations[d.slot]==d.generation,"resident incarnation");
        need(d.slot==m.slot&&d.content==m.content&&d.group==m.group&&d.width==m.width&&d.length==m.length,"resident annotation");
        need(m.first<=d.start&&d.end<=m.last&&initialized[d.slot]>=d.length,"live initialized lease");
        need(d.offset==d.slot*2*B&&d.offset>=0&&int64_t(d.offset)+int64_t(d.length)*d.width<=bytes,"physical extent");
    }
    void run(const Epoch* epochs,int E,const Descriptor* ds,int D,uint32_t* output,Counts& count,Observe obs){
        need(E>=1&&E<=T&&D>=0&&D<=T*P,"plan bounds");int next=0,priorOffset=0;
        for(int e=0;e<E;++e){auto& ep=epochs[e];need(ep.start==next&&ep.end>=ep.start&&ep.end<T&&ep.offset==priorOffset&&ep.count>=0&&ep.count<=P&&int64_t(ep.offset)+ep.count<=D,"epoch bounds");
            int prior=-1;for(int j=0;j<ep.count;++j){auto& d=ds[ep.offset+j];need(d.page>prior&&d.page<P&&d.start==ep.start&&d.end==ep.end,"descriptor order/lease");prior=d.page;}
            next=ep.end+1;priorOffset+=ep.count;}
        need(next==T&&priorOffset==D,"partition end");reset();count={};int ep=0;std::fill(scratch.begin(),scratch.end(),std::numeric_limits<uint32_t>::max());
        for(int t=0;t<T;++t){boundary(t,obs);auto& e=epochs[ep];if(t==e.start){if(e.count==0)published.clear();else published.assign(ds+e.offset,ds+e.offset+e.count);++count.publications;count.copies+=e.count;
            if(obs)obs(2,t,-1,-1,0,-1,0,0,e.count,e.start,e.end,0);}
            for(auto& d:published){validate(d,t);int n=cap(t,pages[d.page]);if(obs)obs(3,t,d.page,d.slot,d.generation,-1,d.width,d.offset,n,d.start,d.end,0);
                for(int i=0;i<n;++i){int off=d.offset+i*d.width;
                    // Volatile byte reads are actual native loads; two-byte lanes are assembled little-endian.
                    auto* ptr=static_cast<volatile uint8_t*>(data+off);uint32_t value=ptr[0];if(d.width==2)value|=uint32_t(ptr[1])<<8;
                    scratch[(size_t(t)*P+d.page)*B+i]=value;++count.loads;count.bytes+=d.width;count.sink=count.sink*1099511628211ULL+value+1;
                    if(obs)obs(4,t,d.page,d.slot,d.generation,i,d.width,off,int(value),d.start,d.end,reinterpret_cast<uintptr_t>(data+off));
                }}
            for(int p=0;p<P;++p)for(int i=0;i<B;++i){size_t k=(size_t(t)*P+p)*B+i;if(mandatory[k]){need(scratch[k]!=std::numeric_limits<uint32_t>::max(),"mandatory lane missing");output[k]=scratch[k];}}
            if(t==e.end)++ep;
        }
        need(ep==E,"execution end");guards();
    }
};
EXPORT void* nb_create(int B,int A,int T,int P,const Page* pages,const int32_t* frontiers,const uint8_t* masks,char* err,int errcap){
    try{need(B>=1&&B<=128&&A>=1&&A<=64&&T>=1&&T<=64&&P>=1&&P<=256&&pages&&frontiers&&masks,"config bounds");auto c=std::make_unique<Context>();c->B=B;c->T=T;c->P=P;
        c->pages.assign(pages,pages+P);c->frontiers.assign(frontiers,frontiers+T);size_t size=size_t(T)*P*B;c->mandatory.assign(masks,masks+size);c->scratch.resize(size);c->published.reserve(P);
        int largest=0;for(int p=0;p<P;++p){auto& m=c->pages[p];need(m.slot>=0&&m.slot<=255&&m.generation>0&&m.content>=0&&m.group>=0&&m.group<=31&&m.first>=0&&m.last>=m.first&&m.last<T&&m.base>=0&&m.length>=1&&m.length<=B&&(m.width==1||m.width==2),"page bounds");
            int end=m.slot*2*B+m.length*m.width;need(A>=17||uint64_t(end)<=(uint64_t(1)<<A),"address width");largest=std::max(largest,m.slot);
            for(int q=0;q<p;++q){auto& o=c->pages[q];if(o.slot!=m.slot)continue;need(o.last<m.first||m.last<o.first,"slot overlap");need(o.first<m.first?o.generation<m.generation:m.generation<o.generation,"generation order");}}
        for(int t=0;t<T;++t){need(frontiers[t]>=0,"frontier");for(int p=0;p<P;++p)for(int i=0;i<B;++i){auto k=(size_t(t)*P+p)*B+i;need(masks[k]<=1,"mask type");if(masks[k])need(c->pages[p].first<=t&&t<=c->pages[p].last&&i<c->cap(t,c->pages[p]),"mandatory lane bound");}}
        c->bytes=(largest+1)*2*B;c->raw=static_cast<uint8_t*>(std::malloc(c->bytes+64));need(c->raw!=nullptr,"allocation failed");c->data=c->raw+32;std::memset(c->raw,0xD3,c->bytes+64);c->reset();return c.release();
    }catch(const std::exception& e){error(err,errcap,e.what());return nullptr;}}
EXPORT int nb_run(void* context,const Epoch* epochs,int E,const Descriptor* descriptors,int D,uint32_t* output,Counts* counts,Observe observe,char* err,int errcap){
    try{need(context&&epochs&&(D==0||descriptors)&&output&&counts,"null argument");static_cast<Context*>(context)->run(epochs,E,descriptors,D,output,*counts,observe);return 0;}catch(const std::exception& e){error(err,errcap,e.what());return 1;}}
// No clock is read by nb_run. This separate entry point is reserved-slot only.
EXPORT int nb_batch(void* context,const Epoch* epochs,int E,const Descriptor* descriptors,int D,uint32_t* output,Counts* counts,int repeats,int64_t* ns,char* err,int errcap){
    try{need(context&&epochs&&(D==0||descriptors)&&output&&counts&&ns&&repeats>=1&&repeats<=16,"batch bounds");auto& c=*static_cast<Context*>(context);
        auto start=std::chrono::steady_clock::now();for(int r=0;r<repeats;++r)c.run(epochs,E,descriptors,D,output,*counts,nullptr);
        *ns=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();return 0;
    }catch(const std::exception& e){error(err,errcap,e.what());return 1;}}
EXPORT int nb_guards(void* context,char* err,int cap){try{need(context!=nullptr,"null context");static_cast<Context*>(context)->guards();return 0;}catch(const std::exception& e){error(err,cap,e.what());return 1;}}
EXPORT int nb_emptytest(void* context,char* err,int cap){try{need(context!=nullptr,"null context");auto& c=*static_cast<Context*>(context);need(std::all_of(c.mandatory.begin(),c.mandatory.end(),[](uint8_t b){return b==0;}),"empty-test domain");
    Epoch e{0,c.T-1,0,0};std::vector<uint32_t> out(c.mandatory.size());Counts count{};need(nb_run(context,&e,1,nullptr,0,out.data(),&count,nullptr,err,cap)==0,"null-descriptor nb_run");need(count.loads==0&&count.bytes==0&&count.publications==1&&count.copies==0,"null-descriptor empty run");return 0;
    }catch(const std::exception& e){error(err,cap,e.what());return 1;}}
EXPORT int nb_selftest(void* context,char* err,int cap){try{need(context!=nullptr,"null context");auto& c=*static_cast<Context*>(context);c.reset();c.boundary(0,nullptr);int p=0;while(p<c.P&&c.pages[p].first!=0)++p;need(p<c.P,"test active page");auto m=c.pages[p];
    Descriptor d{p,m.slot,m.generation,m.content,m.width,m.group,m.slot*2*c.B,m.length,0,0};c.validate(d,0);
    auto reject=[&](const Descriptor& v,int t){bool rejected=false;try{c.validate(v,t);}catch(const std::runtime_error&){rejected=true;}need(rejected,"negative control accepted");};
    int gen=c.generations[m.slot];c.generations[m.slot]=gen==std::numeric_limits<int>::max()?gen-1:gen+1;reject(d,0);c.generations[m.slot]=gen;
    int init=c.initialized[m.slot];c.initialized[m.slot]=0;reject(d,0);c.initialized[m.slot]=init;auto bad=d;bad.offset=c.bytes;reject(bad,0);reject(d,1);c.guards();return 0;
    }catch(const std::exception& e){error(err,cap,e.what());return 1;}}
EXPORT void nb_destroy(void* context){delete static_cast<Context*>(context);}
