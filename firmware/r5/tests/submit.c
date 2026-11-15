#include "submit.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

static unsigned allocs,releases;
static void *make(const void *value)
{
    if (!value)
        return 0;
    unsigned *p = malloc(sizeof(*p));
    assert(p);
    *p = *(const unsigned *)value;
    ++allocs;
    return p;
}
static void dispose(void *p){ ++releases; free(p); }

static int native(struct r5s_state *s,uint32_t cookie,uint32_t source)
{
    uint32_t w = cookie ? r5s_color_word(19,cookie) : 19;
    uint8_t packet[12] = {5,0,0x2f,0x40,0,0,0,0,
                        w&255,(w>>8)&255,(w>>16)&255,(w>>24)&255};
    assert(packet[8] == 19);
    return r5s_accept402f(s,packet,sizeof(packet),source);
}

static struct r5g_lease read_value(struct r5s_state *s,unsigned want)
{
    struct r5g_lease l;
    assert(r5g_owner_read(&s->pool,&s->current,&l) == R5G_OK);
    if (want)
        assert(l.ticket && *(const unsigned *)l.data == want);
    else
        assert(!l.ticket && !l.data);
    return l;
}

int main(void)
{
    struct r5s_state s = {0};
    struct r5s_key a={1,1,1,11}, b={1,2,2,22}, c={1,3,3,33}, d={1,4,4,44},
                   e={1,5,5,55}, off={2,1,0,0};
    unsigned x=1,y=2,z=3,w=4,v=5;
    uint32_t ca,cb,cc,cd,ce,cf,test;
    assert(native(&s,0,R5S_QUEUE_AP) == R5S_STOCK);
    assert(r5s_prepare(&s,a,&x,make,dispose,&ca) == R5S_OK);
    read_value(&s,0);
    assert(r5s_prepare(&s,a,&x,make,dispose,&test) == R5S_OK && test==ca && allocs==1);
    assert(native(&s,ca,R5S_QUEUE_AP+1) == R5S_STALE);
    assert(native(&s,ca,R5S_QUEUE_AP) == R5S_OK);
    assert(native(&s,ca,R5S_QUEUE_AP) == R5S_DUPLICATE);
    assert(r5s_abort(&s,a,dispose) == R5S_DUPLICATE);
    struct r5g_lease photo=read_value(&s,x);

    assert(r5s_prepare(&s,b,&y,make,dispose,&cb) == R5S_OK);
    assert(r5s_prepare(&s,c,0,make,dispose,&cc) == R5S_FAILED);
    assert(native(&s,cb,R5S_QUEUE_AP) == R5S_STALE);
    assert(releases==1);
    struct r5g_lease probe=read_value(&s,x);
    r5g_drop(&s.pool,&probe);

    assert(r5s_prepare(&s,d,&w,make,dispose,&cd) == R5S_OK);
    assert(native(&s,cd,R5S_QUEUE_AP) == R5S_OK);
    struct r5g_lease pending_gamma=read_value(&s,w);
    assert(r5s_prepare(&s,e,&v,make,dispose,&ce) == R5S_OK);
    assert(native(&s,ce,R5S_QUEUE_AP) == R5S_OK);
    struct r5g_lease descriptor=read_value(&s,v);
    struct r5s_key pressure={1,6,3,33};
    assert(r5s_prepare(&s,pressure,&z,make,dispose,&test) == R5S_BUSY);
    assert(!test);
    assert(r5s_prepare(&s,off,0,make,dispose,&cf) == R5S_OK);
    assert(r5s_prepare(&s,pressure,&z,make,dispose,&test) == R5S_STALE);
    assert(native(&s,cf,R5S_QUEUE_AP) == R5S_OK);
    assert(allocs==4 && releases==1);
    assert(r5g_collect(&s.pool,dispose) == 0);
    read_value(&s,0);
    assert(*(const unsigned*)photo.data==1 && *(const unsigned*)pending_gamma.data==4 &&
           *(const unsigned*)descriptor.data==5);
    r5g_drop(&s.pool,&descriptor);
    r5g_drop(&s.pool,&pending_gamma);
    r5g_drop(&s.pool,&photo);
    assert(r5g_collect(&s.pool,dispose) == 3 && allocs==releases);
    puts("PASS: prepare/accept, native identity, duplicate, stale, failure, pressure, Off");
}
