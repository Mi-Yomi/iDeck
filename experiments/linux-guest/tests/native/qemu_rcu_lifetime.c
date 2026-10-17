/* Native pthreads exercise the exact archive registry/RCU/TLS source slice.
 * This condition wait is the native mechanism control, NOT the Swift helper.
 * The Apple executable regression tests the production Foundation helper.
 */
static pthread_mutex_t owner_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t park_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t park_condition = PTHREAD_COND_INITIALIZER;
static pthread_key_t lifetime_key;
static sem_t entered;
static int destroyed;
static struct rcu_reader_data *owner_reader;
static const char *mode;

static void tls_destructor(void *p) {
    assert(p == (void *)1);
    __atomic_add_fetch(&destroyed, 1, __ATOMIC_SEQ_CST);
}
static void *owner(void *unused) {
    (void)unused;
    assert(pthread_setspecific(lifetime_key, (void *)1) == 0);
    rcu_register_thread();
    owner_reader = get_ptr_rcu_reader();
    if (strcmp(mode, "retained") == 0) {
        assert(pthread_mutex_lock(&owner_lock) == 0);
        assert(pthread_mutex_lock(&park_mutex) == 0);
        assert(sem_post(&entered) == 0);
        for (;;) { assert(pthread_cond_wait(&park_condition, &park_mutex) == 0); }
    }
    if (strcmp(mode, "unregister-control") == 0) { rcu_unregister_thread(); }
    return NULL;
}
static void *reader(void *unused) {
    (void)unused;
    rcu_register_thread();
    for (int i = 0; i < 2000; i++) {
        rcu_read_lock(); sched_yield(); rcu_read_unlock();
    }
    rcu_unregister_thread();
    return NULL;
}
int main(int argc, char **argv) {
    assert(argc == 2); mode = argv[1];
    assert(sizeof(void *) == 8);
    assert(offsetof(struct rcu_reader_data, node.le_next) == 16);
    assert(offsetof(struct rcu_reader_data, node.le_prev) == 24);
    assert(pthread_mutex_init(&rcu_registry_lock, NULL) == 0);
    assert(pthread_mutex_init(&rcu_sync_lock, NULL) == 0);
    qemu_event_init(&rcu_gp_event, true);
    assert(pthread_key_create(&lifetime_key, tls_destructor) == 0);
    assert(sem_init(&entered, 0, 0) == 0);
    pthread_t worker;
    assert(pthread_create(&worker, NULL, owner, NULL) == 0);
    if (strcmp(mode, "retained") != 0) {
        assert(pthread_join(worker, NULL) == 0);
        assert(destroyed == 1);
        if (strcmp(mode, "exit-without-unregister") == 0) {
            // Compare addresses only: dereferencing expired TLS would be UB.
            assert(QLIST_FIRST(&registry) == owner_reader);
            puts("STALE_REGISTRY_AFTER_REAL_THREAD_EXIT (expired TLS not dereferenced)");
        } else {
            assert(strcmp(mode, "unregister-control") == 0);
            assert(QLIST_EMPTY(&registry));
            synchronize_rcu();
            puts("UNREGISTER_CONTROL_PASS (test only; no backend teardown contract)");
        }
    } else {
        while (sem_wait(&entered) < 0) { assert(errno == EINTR); }
        pthread_t readers[4];
        for (int i = 0; i < 4; i++) { assert(pthread_create(&readers[i], NULL, reader, NULL) == 0); }
        for (int i = 0; i < 10000; i++) {
            synchronize_rcu();
            // Real spurious/signal wakes do not release the retained thread.
            assert(pthread_cond_signal(&park_condition) == 0);
        }
        for (int i = 0; i < 4; i++) { assert(pthread_join(readers[i], NULL) == 0); }
        assert(__atomic_load_n(&destroyed, __ATOMIC_SEQ_CST) == 0);
        assert(pthread_mutex_trylock(&owner_lock) == EBUSY);
        assert(QLIST_FIRST(&registry) == owner_reader);
        assert(owner_reader->node.le_prev == &registry.lh_first);
        assert(owner_reader->node.le_next == NULL);
        puts("RETAINED_TLS_REGISTRY_PASS (10000 grace periods, 4 native readers, lock retained)");
    }
    fflush(stdout);
    _exit(0); // Only process exit reclaims the retained owner/resources.
}
