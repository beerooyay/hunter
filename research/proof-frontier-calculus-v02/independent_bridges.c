/* Independent exhaustive checker: merge offsets directly and test each modulus.
 * No set-difference identity is used in this checker. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

static const int PRIME[]={2,3,5,7,11,13,17};
static int W[5000][10],O[5000][11],K,N;
static uint64_t hist[65540];
static int is_admissible(const int *A,const int *B,int g){
   const int n=K+1;const int total=2*n;
   for(int pi=0;pi<7;pi++){
      int p=PRIME[pi];if(p>total)break;
      unsigned mask=0;
      for(int j=0;j<n;j++) mask|=1u<<(A[j]%p);
      for(int j=0;j<n;j++) mask|=1u<<((A[K]+g+B[j])%p);
      if(mask==((1u<<p)-1))return 0;
   }
   return 1;
}
int main(int argc,char**argv){
 if(argc!=4)return 2;
 K=atoi(argv[1]);const int limit=atoi(argv[3]);
 FILE*f=fopen(argv[2],"r"); if(!f){perror("fopen");return 2;}
 while(N<5000){
  int ok=1;
  for(int i=0;i<K;i++)if(fscanf(f,"%d",&W[N][i])!=1){ok=0;break;}
  if(!ok)break;
  for(int i=0;i<K;i++)O[N][i+1]=O[N][i]+W[N][i];
  N++;
 }
 fclose(f);
 int best=0;int witness=0,miss=0;
 static int champions[5000][2];
 for(int i=0;i<N;i++)for(int j=0;j<N;j++){
  int g;
  for(g=2;g<=limit;g+=2)if(is_admissible(O[i],O[j],g))break;
  if(g>limit){miss++;continue;}
  hist[g]++;
  if(g>best){best=g;witness=0;}
  if(g==best){if(witness<5000){champions[witness][0]=i;champions[witness][1]=j;}witness++;}
 }
 printf("k=%d motifs=%d pairs=%lld best=%d extremizers=%d missing=%d\n",K,N,(long long)N*N,best,witness,miss);
 for(int ii=0;ii<witness && ii<5000;ii++){
   int i=champions[ii][0], j=champions[ii][1];
   printf("extremizer:");for(int x=0;x<K;x++)printf(" %d",W[i][x]);
   printf(" / ");for(int x=0;x<K;x++)printf(" %d",W[j][x]);printf("\n");
 }
 for(int g=2;g<=limit;g+=2)if(hist[g])printf("%d %llu\n",g,(unsigned long long)hist[g]);
 return miss!=0;
}