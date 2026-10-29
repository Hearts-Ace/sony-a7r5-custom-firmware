/* 只读捕获的控制目录必须位于原始命名空间的同一个tmpfs；不改挂载或权限。 */
struct control_stat {u64 dev,ino;unsigned mode,nlink,uid,gid;u64 rdev,pad;s64 size;unsigned blksize,pad2;u64 blocks,rest[7];};
_Static_assert(sizeof(struct control_stat)==128,"control stat ABI");
static int capture_control_check(int with_child) {
    const char *paths[]={CAPTURE_CONTROL_PARENT,CAPTURE_CONTROL_DIR};
    u64 dev=0;char parent_ns[128],self_ns[128];
    s64 a=sc(78,AT_FDCWD,P("/proc/self/ns/mnt"),P(self_ns),128,0,0);
    s64 b=sc(78,AT_FDCWD,P("/proc/1/ns/mnt"),P(parent_ns),128,0,0);
    if(a<=0||a>=128||a!=b||!same(self_ns,parent_ns,a))return 0;
    for(int i=0;i<(with_child?2:1);i++){
        int fd=(int)open_file(paths[i],RDONLY|16384|NOFOLLOW|CLOEXEC);
        if(fd<0)return 0;
        s64 fs[15];struct control_stat st;
        int valid=sc(44,fd,P(fs),0,0,0,0)==0&&fs[0]==0x01021994&&!(fs[10]&1)&&
            sc(80,fd,P(&st),0,0,0,0)==0&&(st.mode&0170000)==0040000&&st.uid==0;
        if(valid){if(!i)dev=st.dev;else if(st.dev!=dev||(st.mode&0777)!=0700)valid=0;}
        if(close_fd(fd)<0||!valid)return 0;
    }
    return 1;
}
static int capture_control_parent_ready(void){return capture_control_check(0);}
static int capture_control_ready(void){return capture_control_check(1);}
static int capture_control_create(void){
    /* 父目录与票据已核对后才创建；拒绝沿用旧目录或符号链接。 */
    return sc(34,AT_FDCWD,P(CAPTURE_CONTROL_DIR),0700,0,0,0)==0&&capture_control_ready();
}
