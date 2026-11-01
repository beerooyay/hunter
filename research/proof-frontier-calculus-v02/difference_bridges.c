/* Algebraically distinct exhaustive checker using unused-residue difference sets.
 * For p <= number_of_offsets: g is legal iff g in (M_A - M_B - end_A) mod p.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
static const int P[]={2,3,5,7,11,13,17};
static int W[5000][10],O[5000][11],N,K;static uint64_t hist[65540];
static unsigned unoccupied[5000][7];
int main(int argc,char**argv){
 if(argc!=4)return 2;
 K=atoi(argv[1]);int limit=atoi(argv[3]);
 FILE*f=fopen(argv[2],"r");if(!f)return 3;
 while(N<5000){int ok=1;for(int j=0;j<K;j++)if(fscanf(f,"%d",&W[N][j])!=1){ok=0;break;}
   if(!ok)break;
   for(int j=0;j<K;j++){O[N][j+1]=O[N][j]+W[N][j];}N++;
 }
 fclose(f);
 for(int i=0;i<N;i++)for(int z=0;z<7;z++){
   int p=P[z];if(p>2*(K+1))break;
   unsigned mask=(1u<<p)-1;
   for(int j=0;j<K+1;j++) mask &=~(1u<<(O[i][j]%p));
   unoccupied[i][z]=mask;
 }
 int best=0,count=0,miss=0;
 for(int i=0;i<N;i++)for(int j=0;j<N;j++){
   int primes[7],allow[7],n=0;
   for(int z=0;z<7;z++){
     int p=P[z];if(p>2*(K+1))break;
     unsigned a=unoccupied[i][z], b=unoccupied[j][z],r=0;
     for(int x=0;x<p;x++)if(a&(1u<<x))for(int y=0;y<p;y++)if(b&(1u<<y)){
       int g=(x-y-O[i][K])%p;if(g<0)g+=p;r|=1u<<g;
     }
     primes[n]=p;allow[n]=r;n++;
   }
   int g;
   for(g=2;g<=limit;g+=2){
     int z;for(z=0;z<n;z++)if(!(allow[z]&(1u<<(g%primes[z]))))break;
     if(z==n)break;
   }
   if(g>limit){miss++;continue;}
   hist[g]++;if(g>best){best=g;count=0;}if(g==best)count++;
 }
 printf("k=%d motifs=%d pairs=%lld best=%d extremizers=%d missing=%d\n",K,N,(long long)N*N,best,count,miss);
 for(int g=2;g<=limit;g+=2)if(hist[g])printf("%d %llu\n",g,(unsigned long long)hist[g]);
 return miss!=0;
}