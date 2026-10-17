/* Host-test adapters only. Registry, reader struct, TLS, lists and grace-period
 * algorithm come verbatim from the SHA-verified QEMU archive, not this file.
 * QEMU event/mutex operations use native pthreads; atomic operations use GCC's
 * builtins. Full fences stand in for QEMU's optional membarrier optimization.
 * No GLib, RCU callbacks, backend, BQL implementation or VM is linked here.
 */
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <semaphore.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "qemu/queue.h"
#include "qemu/coroutine-tls.h"
typedef struct Error Error;
#include "qemu/notify.h"

typedef pthread_mutex_t QemuMutex;
typedef struct {
    pthread_mutex_t mutex;
    pthread_cond_t condition;
    bool set;
} QemuEvent;

static void qemu_mutex_lock(QemuMutex *m) { assert(pthread_mutex_lock(m) == 0); }
static void qemu_mutex_unlock(QemuMutex *m) { assert(pthread_mutex_unlock(m) == 0); }
static void qemu_event_init(QemuEvent *e, bool set) {
    assert(pthread_mutex_init(&e->mutex, NULL) == 0);
    assert(pthread_cond_init(&e->condition, NULL) == 0);
    e->set = set;
}
static void qemu_event_reset(QemuEvent *e) {
    qemu_mutex_lock(&e->mutex); e->set = false; qemu_mutex_unlock(&e->mutex);
}
static void qemu_event_set(QemuEvent *e) {
    qemu_mutex_lock(&e->mutex); e->set = true;
    assert(pthread_cond_broadcast(&e->condition) == 0); qemu_mutex_unlock(&e->mutex);
}
static void qemu_event_wait(QemuEvent *e) {
    qemu_mutex_lock(&e->mutex);
    while (!e->set) { assert(pthread_cond_wait(&e->condition, &e->mutex) == 0); }
    qemu_mutex_unlock(&e->mutex);
}
static QemuMutex *locked(QemuMutex *m) { qemu_mutex_lock(m); return m; }
static void unlock_guard(QemuMutex **m) { qemu_mutex_unlock(*m); }
#define CONCAT_(a, b) a##b
#define CONCAT(a, b) CONCAT_(a, b)
#define QEMU_LOCK_GUARD(m) __attribute__((cleanup(unlock_guard))) \
    QemuMutex *CONCAT(guard_, __LINE__) = locked(m)
#define qatomic_read(p) __atomic_load_n(p, __ATOMIC_RELAXED)
#define qatomic_set(p, v) __atomic_store_n(p, v, __ATOMIC_RELAXED)
#define qatomic_store_release(p, v) __atomic_store_n(p, v, __ATOMIC_RELEASE)
#define smp_mb_global() __atomic_thread_fence(__ATOMIC_SEQ_CST)
#define smp_mb_placeholder() __atomic_thread_fence(__ATOMIC_SEQ_CST)
#define unlikely(x) __builtin_expect(!!(x), 0)
void notifier_list_notify(NotifierList *list, void *data) {
    (void)data;
    assert(QLIST_EMPTY(&list->notifiers));
}
