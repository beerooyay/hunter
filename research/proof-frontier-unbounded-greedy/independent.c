/* Independent residue-only checker. Does NOT construct large integers Q.
   The CRT construction makes other small-prime residues collapse to three phases.
   Compile: cc -O2 -std=c11 -Wall -Wextra independent.c -o independent
*/
#include <stdio.h>
#include <string.h>
#include <assert.h>

static int prime(int n) {if(n<2)return 0;for(int q=2;q*q<=n;q++)if(n%q==0)return 0;return 1;}
static int allowed_at_p(int p,int g1,int g2,int stages) {
  int used[2048]={0};
  if(p>2048)return 0;
  for(int r=0;r<p;r++) if(r!=1 && r!=7)used[r]=1;
  for(int r=0;r<p;r++) if(r!=p-1 && r!=3)used[(r+g1)%p]=1;
  if(stages==3)for(int r=0;r<p;r++) if(r!=1)used[(r+g1+g2)%p]=1;
  for(int r=0;r<p;r++)if(!used[r])return 1;
  return 0;
}
static int allowed_other_primes(int g1,int g2,int stages){
  /* Every original motif has all offsets 0 mod q for q != p <= N. */
  if(g1%2!=0 || g1<=0 || (stages==3 && (g2<=0 || g2%2!=0)))return 0;
  if(stages==2)return 1; /* at most 2 phase classes; never cover mod >= 3 */
  /* modulo 3 is the only possible other obstruction */
  int seen[3]={0}; seen[0]=1;seen[g1%3]=1;seen[(g1+g2)%3]=1;
  return !(seen[0] && seen[1] && seen[2]);
}
static int allowed(int p,int g1,int g2,int stages){
 return allowed_at_p(p,g1,g2,stages)&&allowed_other_primes(g1,g2,stages);
}
int main(void){
 int cases=0;
 for(int p=13;p<=997;p++)if(prime(p)&&p%3==1){
  int g1=0,g2=0;
  for(int g=2;g<=2*p+6;g+=2)if(allowed(p,g,0,2)){g1=g;break;}
  for(int g=2;g<=2*p+6;g+=2)if(allowed(p,g1,g,3)){g2=g;break;}
  if(g1!=2 || g2!=2*p-2 || allowed(p,2,2,3) || !allowed(p,4,2,3)){
    printf("FAILED p=%d g1=%d g2=%d\n",p,g1,g2);return 1;
  }
  cases++;
 }
 printf("PASS: independent residue checker %d primes p ≡ 1 mod 3, 13 <= p <= 997\n",cases);
 return 0;
}