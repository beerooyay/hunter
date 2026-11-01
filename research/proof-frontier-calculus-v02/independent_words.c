/* Independent motif generator and verifier (no Python). */
#include <stdio.h>
#include <stdlib.h>
static int P[]={2,3,5,7,11,13,17,19};
int main(int argc,char**argv){
 if(argc!=2)return 2;
 int k=atoi(argv[1]);if(k<1||k>8)return 3;
 const int abc[5]={2,4,6,8,10};
 int count=0, total=1;
 for(int z=0;z<k;z++)total*=5;
 for(int m=0;m<total;m++){
  int w[10],a[11]={0},t=m;
  for(int i=k-1;i>=0;i--){w[i]=abc[t%5];t/=5;}
  for(int i=0;i<k;i++)a[i+1]=a[i]+w[i];
  int good=1;
  for(int zz=0;zz<8;zz++){
   int p=P[zz];if(p>k+1)break;
   unsigned mask=0;
   for(int i=0;i<k+1;i++)mask|=1u<<(a[i]%p);
   if(mask==(1u<<p)-1){good=0;break;}
  }
  if(!good)continue;
  for(int i=0;i<k;i++)printf(i==k-1?"%d\n":"%d ",w[i]);
  count++;
 }
 fprintf(stderr,"verified motifs = %d\n",count);
 return 0;
}