#include "generation.h"

#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>

struct value { uint32_t id, inverse; };
static unsigned created, disposed;
static atomic_uint observations;
static struct r5g_pool pool;
static uint32_t live;
static atomic_int stop;

static struct r5g_lease prepare(struct r5g_pool *p, uint32_t ticket)
{
    struct value *v = malloc(sizeof(*v));
    assert(v);
    *v = (struct value){ticket, ~ticket};
    ++created;
    return r5g_publish(p, ticket, v);
}

static void check(struct r5g_lease lease, uint32_t want)
{
    const struct value *v = lease.data;
    assert(lease.ticket == want);
    if (want)
        assert(v && v->id == want && v->inverse == ~want);
    else
        assert(!v);
}

static void dispose(void *data)
{
    struct value *v = data;
    assert(v && v->id && v->inverse == ~v->id);
    v->id = 0;
    ++disposed;
    free(v);
}

static void staged(void)
{
    uint32_t first, second, third, aborted, unavailable, preview = 0, shot = 0, clone = 0;
    struct r5g_pool p = {0};
    struct r5g_lease l, task, descendant, temp, off = {0};
    assert(!r5g_begin(&p, &first));
    assert(!r5g_owner_read(&p, &preview, &l));
    check(l, 0);
    l = prepare(&p,first);
    r5g_owner_replace(&p,&preview,&l);
    assert(!r5g_owner_read(&p,&preview,&l));
    check(l,first);
    r5g_owner_replace(&p,&shot,&l);
    assert(!r5g_owner_read(&p,&shot,&l));
    r5g_owner_replace(&p,&clone,&l);

    assert(!r5g_begin(&p,&aborted));
    check(r5g_pin(&p,aborted),0);
    r5g_abort(&p,aborted); /* allocator failure must not disturb preview */
    assert(!r5g_owner_read(&p,&preview,&l));
    check(l,first);
    r5g_drop(&p,&l);

    assert(!r5g_begin(&p,&second));
    l = prepare(&p,second);
    assert(!r5g_owner_read(&p,&preview,&temp));
    check(temp,first); /* prepared is not accepted */
    r5g_drop(&p,&temp);
    r5g_owner_replace(&p,&preview,&l);

    assert(!r5g_owner_read(&p,&preview,&task));
    check(task,second);
    assert(!r5g_owner_read(&p,&clone,&descendant));
    check(descendant,first);
    assert(!r5g_begin(&p,&third));
    l = prepare(&p,third);
    assert(r5g_begin(&p,&unavailable) == R5G_BUSY && !unavailable);
    r5g_owner_replace(&p,&preview,&l);
    r5g_owner_replace(&p,&preview,&off); /* Off while two jobs keep old leases */
    assert(r5g_collect(&p,dispose) == 1);
    check(task,second);
    check(descendant,first);

    r5g_drop(&p,&task);
    r5g_owner_replace(&p,&shot,&off);
    r5g_owner_replace(&p,&clone,&off);
    assert(r5g_collect(&p,dispose) == 1);
    check(descendant,first);
    r5g_drop(&p,&descendant);
    assert(r5g_collect(&p,dispose) == 1);
    assert(!r5g_begin(&p,&third) && (third&3u) == (first&3u));
    l = prepare(&p,third);
    check(r5g_pin(&p,first),0);
    check(l,third);
    r5g_drop(&p,&l);
    assert(r5g_collect(&p,dispose) == 1);
    p.serial = R5G_SERIAL_MAX - 1;
    assert(!r5g_begin(&p,&third));
    r5g_abort(&p,third);
    assert(r5g_begin(&p,&unavailable) == R5G_EXHAUSTED);
    assert(created == disposed);
}

static void *consumer(void *unused)
{
    (void)unused;
    while (!atomic_load_explicit(&stop,memory_order_acquire)) {
        struct r5g_lease l;
        if (r5g_owner_read(&pool,&live,&l) == R5G_OK && l.ticket) {
            check(l,l.ticket);
            atomic_fetch_add_explicit(&observations,1,memory_order_relaxed);
            r5g_drop(&pool,&l);
        }
    }
    return 0;
}

static void concurrent(void)
{
    pthread_t readers[4];
    for (unsigned i=0;i<4;i++)
        assert(!pthread_create(&readers[i],0,consumer,0));
    for (unsigned i=0;i<200000;i++) {
        uint32_t t;
        struct r5g_lease l = {0};
        r5g_collect(&pool,dispose);
        if (i % 13 == 0) {
            r5g_owner_replace(&pool,&live,&l);
        } else if (!r5g_begin(&pool,&t)) {
            l = prepare(&pool,t);
            r5g_owner_replace(&pool,&live,&l);
        }
    }
    struct r5g_lease off = {0};
    r5g_owner_replace(&pool,&live,&off);
    atomic_store_explicit(&stop,1,memory_order_release);
    for (unsigned i=0;i<4;i++)
        assert(!pthread_join(readers[i],0));
    r5g_collect(&pool,dispose);
    assert(created == disposed);
    assert(created > 10000 && atomic_load(&observations) > 100);
}

int main(void)
{
    staged();
    concurrent();
    printf("PASS: created=%u released=%u reader_validations=%u\n",
           created,disposed,atomic_load(&observations));
}
