/* Independent prime occurrence evaluator: no probability model or bridge selector here.
   C11, no dependencies. Counts simultaneous tuples and *consecutive* prime motifs. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#define MAXK 16
#define MAX_PATTERNS 10000
#define MAXID 80

typedef struct { char id[MAXID], pair[MAXID], policy[24]; int k; uint32_t off[MAXK]; uint64_t tuples, consecutive; } Row;
static Row rows[MAX_PATTERNS];
static unsigned char *prime;
static uint32_t *prefix;
static uint32_t *starts;

int main(int argc,char **argv){
 if(argc!=3 && argc!=4){fprintf(stderr,"usage: count_patterns candidates.tsv max_start [min_start]\n");return 2;}
 uint32_t N=(uint32_t)strtoul(argv[2],NULL,10);
 uint32_t MIN=argc==4?(uint32_t)strtoul(argv[3],NULL,10):100003;
 if(MIN<2 || MIN>N){fprintf(stderr,"bad minimum start\n");return 2;}
 if(N<1000 || N>70000000){fprintf(stderr,"max_start out of range\n");return 2;}
 FILE *f=fopen(argv[1],"r");if(!f){perror("candidates");return 2;}
 int nr=0;uint32_t maxoff=0;
 while(nr<MAX_PATTERNS){
   Row *r=&rows[nr];int n=fscanf(f,"%79s %79s %23s %d",r->id,r->pair,r->policy,&r->k);
   if(n==EOF)break;
   if(n!=4 || r->k<2 || r->k>MAXK){fprintf(stderr,"bad header\n");return 3;}
   for(int j=0;j<r->k;j++){
     if(fscanf(f,"%u",&r->off[j])!=1){fprintf(stderr,"bad offset\n");return 3;}
     if(j && r->off[j]<=r->off[j-1]){fprintf(stderr,"nonascending offsets\n");return 3;}
   }
   if(r->off[0]!=0){fprintf(stderr,"missing base offset\n");return 3;}
   if(r->off[r->k-1]>maxoff)maxoff=r->off[r->k-1];
   nr++;
 }
 fclose(f);
 if(nr==MAX_PATTERNS){fprintf(stderr,"too many patterns\n");return 3;}
 uint32_t LIM=N+maxoff;
 prime=malloc((size_t)LIM+1);prefix=malloc(((size_t)LIM+2)*sizeof(*prefix));starts=malloc(((size_t)N+1)*sizeof(*starts));
 if(!prime || !prefix || !starts){fprintf(stderr,"allocation failure\n");return 3;}
 memset(prime,1,(size_t)LIM+1);prime[0]=prime[1]=0;
 for(uint64_t i=2;i*i<=LIM;i++)if(prime[i])for(uint64_t j=i*i;j<=LIM;j+=i)prime[j]=0;
 prefix[0]=0;for(uint32_t i=0;i<=LIM;i++)prefix[i+1]=prefix[i]+prime[i];
 uint32_t ns=0;for(uint32_t i=MIN;i<=N;i++) if(prime[i])starts[ns++]=i;
 fprintf(stderr,"prime starts=%u candidates=%d span<=%u\n",ns,nr,maxoff);
 puts("id,pair,policy,tuples,consecutive");
 for(int x=0;x<nr;x++){
   Row *r=&rows[x];
   for(uint32_t y=0;y<ns;y++){
     uint32_t p=starts[y];int works=1;
     for(int j=1;j<r->k;j++)if(!prime[p+r->off[j]]){works=0;break;}
     if(works){r->tuples++;
       if(prefix[p+r->off[r->k-1]+1]-prefix[p]==(uint32_t)r->k)r->consecutive++;
     }
   }
   printf("%s,%s,%s,%llu,%llu\n",r->id,r->pair,r->policy,(unsigned long long)r->tuples,(unsigned long long)r->consecutive);
 }
 return 0;
}