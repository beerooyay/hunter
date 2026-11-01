/* Exhaustive shortest-bridge versus globally optimal two-bridge comparison.
 * Each 3-way configuration has 3(k+1) prime offsets; only primes <= that count can obstruct.
 * The CRT period bounds how far each positive bridge need be searched.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
static const int P[]={2,3,5,7,11,13,17,19};
static int W[5000][10],O[5000][11],K,N;
static unsigned long long total_regret=0,better=0,equal=0,total_greedy=0,total_opt=0;
static int max_saving=-1,champ_i,champ_j,champ_k,champ_gg,champ_gh,champ_og,champ_oh;
static int legal2(const int *A,const int *B,int g){
 int n=K+1;for(int pi=0;pi<8;pi++){
  int p=P[pi];if(p>2*n)break;
  unsigned mask=0;
  for(int j=0;j<n;j++) mask|=1u<<(A[j]%p);
  for(int j=0;j<n;j++) mask|=1u<<((A[K]+g+B[j])%p);
  if(mask==((1u<<p)-1))return 0;
 }
 return 1;
}
static int legal3(const int *A,const int *B,const int *C,int g,int h){
 int n=K+1,shiftB=A[K]+g,shiftC=shiftB+B[K]+h;
 for(int pi=0;pi<8;pi++){
  int p=P[pi];if(p>3*n)break;
  unsigned mask=0;
  for(int j=0;j<n;j++) mask|=1u<<(A[j]%p);
  for(int j=0;j<n;j++) mask|=1u<<((shiftB+B[j])%p);
  for(int j=0;j<n;j++) mask|=1u<<((shiftC+C[j])%p);
  if(mask==((1u<<p)-1))return 0;
 }
 return 1;
}
static int prime_period(int m){int q=1;for(int i=0;i<8;i++){if(P[i]>m)break;q*=P[i];}return q;}
int main(int argc,char**argv){
 if(argc!=3)return 2;
 K=atoi(argv[1]);FILE*f=fopen(argv[2],"r");if(!f)return 2;
 while(N<5000){int ok=1;for(int z=0;z<K;z++)if(fscanf(f,"%d",&W[N][z])!=1){ok=0;break;}if(!ok)break;
 for(int z=0;z<K;z++){O[N][z+1]=O[N][z]+W[N][z];}N++;}fclose(f);
 int period2=prime_period(2*(K+1));int period3=prime_period(3*(K+1));
 fprintf(stderr,"k=%d motifs=%d period2=%d period3=%d\n",K,N,period2,period3);
 int checked=0;
 for(int i=0;i<N;i++)for(int j=0;j<N;j++){
  int first_g=-1;
  for(int g=2;g<=period2;g+=2)if(legal2(O[i],O[j],g)){first_g=g;break;}
  if(first_g<0){fprintf(stderr,"NO FIRST G\n");return 3;}
  for(int k=0;k<N;k++){
   int first_h=-1;
   for(int h=2;h<=period3;h+=2)if(legal3(O[i],O[j],O[k],first_g,h)){first_h=h;break;}
   if(first_h<0){fprintf(stderr,"NO FIRST H\n");return 4;}
   int score=first_g+first_h;
   int bg=-1,bh=-1;
   for(int total=4;total<=score;total+=2){
    for(int g=2;g<total;g+=2){int h=total-g;
      if(legal3(O[i],O[j],O[k],g,h)){bg=g;bh=h;break;}
    }
    if(bg>0)break;
   }
   if(bg<0){fprintf(stderr,"NO GLOBAL\n");return 5;}
   int opt=bg+bh,saving=score-opt;
   if(saving<0){fprintf(stderr,"NEGATIVE\n");return 6;}
   if(saving>0)better++;else equal++;
   total_greedy+=score;total_opt+=opt;total_regret+=saving;
   if(saving>max_saving){max_saving=saving;champ_i=i;champ_j=j;champ_k=k;champ_gg=first_g;champ_gh=first_h;champ_og=bg;champ_oh=bh;}
   checked++;
  }
 }
 printf("k %d motifs %d triples %d global_better %llu ties %llu mean_greedy %.6f mean_global %.6f mean_saving %.6f max_saving %d\n",K,N,checked,better,equal,(double)total_greedy/checked,(double)total_opt/checked,(double)total_regret/checked,max_saving);
 printf("worst_words:");for(int z=0;z<K;z++)printf(" %d",W[champ_i][z]);printf(" | ");for(int z=0;z<K;z++)printf(" %d",W[champ_j][z]);printf(" | ");for(int z=0;z<K;z++)printf(" %d",W[champ_k][z]);printf("\n");
 printf("worst_greedy %d %d worst_global %d %d\n",champ_gg,champ_gh,champ_og,champ_oh);
 return 0;
}