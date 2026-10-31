#include "survivors.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
 uint64_t state=123, bits[70]; uint32_t out[4100];
 for (unsigned limit=0; limit<=4096; ++limit) {
  for (unsigned mode=0; mode<3; ++mode) {
   for(unsigned w=0;w<70;++w) {state^=state<<13;state^=state>>7;state^=state<<17;bits[w]=mode==0?0:mode==1?UINT64_MAX:state;}
   out[limit]=0xdeadbeef;
   uint64_t n=hunter_survivors(bits,2,limit,out), j=0;
   for(unsigned i=1;i<=limit;++i) if(!(bits[2+i/64]>>(i%64)&1)) {assert(j<n);assert(out[j++]==i);}
   assert(j==n);assert(out[limit]==0xdeadbeef);
  }
 }
 puts("PASS: 12291 bitset cases, boundary offsets and output canaries");
}
