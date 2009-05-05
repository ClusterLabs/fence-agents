/** @file fence_nss_wrapper.c - Main source code of hobbit like tool with
  support for NSS (SSL) connection.
*/
#include <stdio.h>
#include <nss.h>
#include <ssl.h>
#include <prio.h>
#include <prnetdb.h>
#include <prerror.h>
#include <prinit.h>
#include <getopt.h>
#include <libgen.h>

/*---- CONSTANTS -------------*/

/** Default operation = connect and telnet*/
#define OPERATION_DEFAULT 0
/** Operation display help*/
#define OPERATION_HELP 1

/** Default mode of connection. Try first found working address*/
#define MODE_DEFAULT 3
/** Use only IPv4*/
#define MODE_IP4MODE 1
/** Use only IPv6*/
#define MODE_IP6MODE 2
/** Use RAW mode - no change of \r and \n to \r\n*/
#define MODE_RAW     4
/** Use non-secure mode (without SSL, only pure socket)*/
#define MODE_NO_SSL  8

/*------ Functions ---------------*/

/** Return port inserted in string. Fuction tests, if port is integer, and than return
  integer value of string. Otherwise, it will use /etc/services.  On fail, it returns
  port -1.
  @param port_s Input port or service name
  @return port number (converted with ntohs) on success, otherwise -1.
*/
static int return_port(char *port_s) {
  char *end_c;
  int res;
  struct servent *serv;

  res=strtol(port_s,&end_c,10);

  if (*end_c=='\0') return res;

  /*It's not number, so try service name*/
  serv=getservbyname(port_s,NULL);

  if (serv==NULL) return -1;

  return ntohs(serv->s_port);
}

/** Hook handler for bad certificate (because we have no DB, EVERY certificate is bad).
  Returned value is always SECSuccess = it's ok certificate.
  @param arg NULL value
  @param fd socket cased error
  @return SECSuccess.
*/
static SECStatus nss_bad_cert_hook(void *arg,PRFileDesc *fd) {
  return SECSuccess;
}

/** Display last NSPR/NSS error code and user readable message.
*/
static void print_nspr_error(void) {
  fprintf(stderr,"Error (%d): %s\n",PR_GetError(),PR_ErrorToString(PR_GetError(),PR_LANGUAGE_I_DEFAULT));
}

/** Initialize NSS. NSS is initialized without DB and with
  domnestic policy.
  @return 1 on success, otherwise 0.
*/
static int init_nss(void) {
  if ((NSS_NoDB_Init(NULL)!=SECSuccess) ||
      (NSS_SetDomesticPolicy()!=SECSuccess)) {
    print_nspr_error();

    return 0;
  }

  SSL_ClearSessionCache();

  return 1;
}

/** Create socket. If ssl is >0, socket is ssl enabled.
  @param ssl Enable ssl (Client, SSL2+3, no TLS, compatible hello) if PR_TRUE, otherwise no.
  @param ipv6 New socket will be IPv4 if this value is 0, otherwise it will be ipv6
  @return NULL on error, otherwise socket.
*/
static PRFileDesc *create_socket(int ssl,int ipv6) {
  PRFileDesc *res_socket;

  res_socket=PR_OpenTCPSocket((ipv6?PR_AF_INET6:PR_AF_INET));
  if (res_socket==NULL) {
    print_nspr_error();

    return NULL;
  }

  if (!ssl) return res_socket;

  if (!(res_socket=SSL_ImportFD(NULL,res_socket))) {
    print_nspr_error();

    return NULL;
  }

  if ((SSL_OptionSet(res_socket,SSL_SECURITY,ssl)!=SECSuccess) ||
      (SSL_OptionSet(res_socket,SSL_HANDSHAKE_AS_SERVER,PR_FALSE)!=SECSuccess) ||
      (SSL_OptionSet(res_socket,SSL_HANDSHAKE_AS_CLIENT,PR_TRUE)!=SECSuccess) ||
      (SSL_OptionSet(res_socket,SSL_ENABLE_SSL2,ssl)!=SECSuccess) ||
      (SSL_OptionSet(res_socket,SSL_ENABLE_SSL3,ssl)!=SECSuccess) ||
      (SSL_OptionSet(res_socket,SSL_ENABLE_TLS,PR_FALSE)!=SECSuccess) ||
      (SSL_OptionSet(res_socket,SSL_V2_COMPATIBLE_HELLO,ssl)!=SECSuccess) ||
      (SSL_SetPKCS11PinArg(res_socket,NULL)==-1) ||
      (SSL_AuthCertificateHook(res_socket,SSL_AuthCertificate,CERT_GetDefaultCertDB())!=SECSuccess) ||
      (SSL_BadCertHook(res_socket,nss_bad_cert_hook,NULL)!=SECSuccess)) {
    print_nspr_error();

    if (PR_Close(res_socket)!=PR_SUCCESS) {
      print_nspr_error();
    }

    return NULL;
  }

  return res_socket;
}

/** Create socket and connect to it.
  @param hostname Hostname to connect
  @param port Port name/number to connect
  @param mode Connection mode. Bit-array of MODE_NO_SSL, MODE_IP6MODE, MODE_IP4MODE.
  @return NULL on error, otherwise connected socket.
*/
static PRFileDesc *create_connected_socket(char *hostname,int port,int mode) {
  PRAddrInfo *addr_info;
  void *addr_iter;
  PRNetAddr addr;
  PRFileDesc *localsocket;
  int can_exit,valid_socket;
  PRUint16 af_spec;

  localsocket=NULL;

  addr_info=NULL;

  af_spec=PR_AF_UNSPEC;

  if (!(mode&MODE_IP6MODE)) af_spec=PR_AF_INET;

  addr_info=PR_GetAddrInfoByName(hostname,af_spec,PR_AI_ADDRCONFIG);

  if (addr_info == NULL) {
    print_nspr_error();
    return NULL;
  }

  /*We have socket -> enumerate and try to connect*/
  addr_iter=NULL;
  can_exit=0;
  valid_socket=0;

  while (!can_exit) {
    addr_iter=PR_EnumerateAddrInfo(addr_iter,addr_info,port,&addr);

    if (addr_iter==NULL) {
      can_exit=1;
    } else {
      if ((PR_NetAddrFamily(&addr)==PR_AF_INET && (mode&MODE_IP4MODE)) ||
          (PR_NetAddrFamily(&addr)==PR_AF_INET6 && (mode&MODE_IP6MODE))) {
        /*Type of address is what user want, try to create socket and make connection*/

        /*Create socket*/
        localsocket=create_socket(!(mode&MODE_NO_SSL),(PR_NetAddrFamily(&addr)==PR_AF_INET6));

        if (localsocket) {
          /*Try to connect*/
          if (PR_Connect(localsocket,&addr,PR_INTERVAL_NO_TIMEOUT)==PR_SUCCESS) {
            /*Force handshake*/
            if ((!(mode&MODE_NO_SSL)) && SSL_ForceHandshake(localsocket)!=SECSuccess) {
              /*Handhake failure -> fail*/
              print_nspr_error();
              if (PR_Close(localsocket)!=PR_SUCCESS) {
                print_nspr_error();
                can_exit=1;
              }
              localsocket=NULL;
            }

            /*Socket is connected -> we can return it*/
            can_exit=1;
          } else {
            /*Try another address*/
            if (PR_Close(localsocket)!=PR_SUCCESS) {
              print_nspr_error();
              can_exit=1;
            }
            localsocket=NULL;
          }
        }
      }
    }
  }

  if (!localsocket) {
    /*Socket is unvalid -> we don't found any usable address*/
    fprintf(stderr,"Can't connect to host %s on port %d!\n",hostname,port);
  }

  PR_FreeAddrInfo(addr_info);

  return localsocket;
}

/** Parse arguments from command line.
  @param argc Number of arguments in argv
  @param argv Array of arguments
  @param mode Pointer to int will be filled with OPERATION_DEFAULT or OPERATION_HELP.
  @param mode Pointer to int will be filled with MODE_DEFAULT, MODE_IP4MODE or MODE_IP4MODE.
  @return 1 on success, otherwise 0.
*/
static int parse_cli(int argc,char *argv[],int *operation,int *mode,char **hostname,char **port) {
  int opt;

  *operation=OPERATION_DEFAULT;
  *mode=MODE_DEFAULT;
  *port=NULL;
  *hostname=NULL;

  while ((opt=getopt(argc,argv,"h46rz"))!=-1) {
    switch (opt) {
      case 'h':
        *operation=OPERATION_HELP;

        return 0;
      break;

      case '4':
        (*mode)&=~MODE_IP6MODE;
        (*mode)|=MODE_IP4MODE;
      break;

      case '6':
        (*mode)&=~MODE_IP4MODE;
        (*mode)|=MODE_IP6MODE;
      break;

      case 'r':
        (*mode)|=MODE_RAW;
      break;

      case 'z':
        (*mode)|=MODE_NO_SSL;
      break;

      default:
        return 0;
      break;
    }
  }

  if (argc-optind<2) {
    fprintf(stderr,"Hostname and port is expected!\n");

    return 0;
  }

  *hostname=argv[optind];
  *port=argv[optind+1];

  return 1;
}

/** Show usage of application.
  @param pname Name of program (usually basename of argv[0])
*/
static void show_usage(char *pname) {
  printf("usage: %s [options] hostname port\n", pname);
  printf("   -4             Force to use IPv4\n");
  printf("   -6             Force to use IPv6\n");
  printf("   -r             Use RAW connection (don't convert \\r and \\n characters)\n");
  printf("   -z             Don't use SSL connection (use pure socket)\n");
  printf("   -h             Show this help\n");
}

/** Convert End Of Lines (Unix \n, Macs \r or DOS/Win \r\n) to \r\n.
  @param in_buffer Input buffer
  @param in_size Input buffer size
  @param out_buffer Output buffer (must be prealocated). Should be (2*in_size) (in worst case)
  @param out_size There will be size of out_buffer
  @param in_state Internal state of finite automata. First call should have this 0, other calls
    shouldn't change this value. After end of file, you may add to this value +100 and call this
    again, to make sure of proper end (in_buffer can be in this case everything, including NULL).
*/
static void convert_eols(char *in_buffer,int in_size,char *out_buffer,int *out_size,int *in_state) {
  int in_pos,out_pos;
  int status;
  char in_char;

  out_pos=0;
  status=*in_state;

  if (status==100 || status==101) {
    if (status==101) {
      out_buffer[out_pos++]='\r';
      out_buffer[out_pos++]='\n';
    }
  } else {
    for (in_pos=0;in_pos<in_size;in_pos++) {
      in_char=in_buffer[in_pos];

      switch (status) {
        case 0:
          if (in_char=='\r') status=1;
          if (in_char=='\n') {
            out_buffer[out_pos++]='\r';
            out_buffer[out_pos++]='\n';
          }
          if ((in_char!='\r') && (in_char!='\n')) out_buffer[out_pos++]=in_char;
        break;

        case 1:
          out_buffer[out_pos++]='\r';
          out_buffer[out_pos++]='\n';

          if (in_char!='\n') out_buffer[out_pos++]=in_char;

          status=0;
        break;
      }
    }
  }

  *out_size=out_pos;
  *in_state=status;
}

/** Start polling cycle.
  @param socket Network connected socket.
  @param mode Bit-array of MODE_*. This function take care on MODE_RAW.
  @return 0 on failure, otherwise 1
*/
static int poll_cycle(PRFileDesc *localsocket,int mode) {
  PRPollDesc pool[2];
  char buffer[1024],buffer_eol[1024*2];
  int readed_bytes;
  int can_exit;
  int res;
  int bytes_to_write;
  int eol_state;

  can_exit=0;
  eol_state=0;

  /* Fill pool*/
  pool[1].fd=localsocket;
  pool[0].fd=PR_STDIN;
  pool[0].in_flags=pool[1].in_flags=PR_POLL_READ;
  pool[0].out_flags=pool[1].out_flags=0;

  while (!can_exit) {
    res=(PR_Poll(pool,sizeof(pool)/sizeof(PRPollDesc),PR_INTERVAL_NO_TIMEOUT));

    if (res==-1) {
      print_nspr_error();

      return 0;
    }

    if (pool[1].out_flags&PR_POLL_READ) {
      /*We have something in socket*/
      if ((readed_bytes=PR_Read(pool[1].fd,buffer,sizeof(buffer)))>0) {
        if (PR_Write(PR_STDOUT,buffer,readed_bytes)!=readed_bytes) {
          print_nspr_error();

          return 0;
        }
      } else {
        /*End of stream -> quit*/
        can_exit=1;
      }
    }

    if (pool[0].out_flags&(PR_POLL_READ|PR_POLL_HUP)) {
      /*We have something in stdin*/
      if ((readed_bytes=PR_Read(pool[0].fd,buffer,sizeof(buffer)))>0) {

        if (!(mode&MODE_RAW)) {
          convert_eols(buffer,readed_bytes,buffer_eol,&bytes_to_write,&eol_state);
        } else
          bytes_to_write=readed_bytes;

        if (PR_Write(pool[1].fd,(mode&MODE_RAW?buffer:buffer_eol),bytes_to_write)!=bytes_to_write) {
          print_nspr_error();

          return 0;
        }
      } else {
        /*End of stream -> send EOL (if needed)*/
        if (!(mode&MODE_RAW)) {
          eol_state+=100;
          convert_eols(NULL,0,buffer_eol,&bytes_to_write,&eol_state);
          if (PR_Write(pool[1].fd,buffer_eol,bytes_to_write)!=bytes_to_write) {
            print_nspr_error();

            return 0;
          }
        }
      }
    }

    pool[0].out_flags=pool[1].out_flags=0;
  } /*while (!can_exit)*/

  return 1;
}

static void atexit_handler(void) {
  if (PR_Initialized())
    PR_Cleanup();

  if (fclose(stdout)!=0) {
    fprintf(stderr,"Can't close stdout!\n");

    exit(1);
  }
}

/** Entry point of application.
  @param argc Number of arguments on command line
  @param argv Array of strings with arguments from command line
  @return 0 on success, otherwise >0.
*/
int main(int argc,char *argv[]) {
  int mode,operation;
  char *hostname, *port;
  char *pname;
  int port_n;
  PRFileDesc *fd_socket;
  int res;

  pname=basename(argv[0]);

  atexit(atexit_handler);

  if (!parse_cli(argc,argv,&operation,&mode,&hostname,&port) || operation==OPERATION_HELP) {
    show_usage(pname);

    if (operation!=OPERATION_HELP) return 1;

    return 0;
  }

  if ((port_n=return_port(port))==-1) {
    fprintf(stderr,"Error. Unknown port number/name %s!\n",port);

    return 1;
  }

  if (!(mode&MODE_NO_SSL)) {
    if (!init_nss()) return 1;
  }

  if (!(fd_socket=create_connected_socket(hostname,port_n,mode)))
    return 1;

  res=poll_cycle(fd_socket,mode);

  if (PR_Close(fd_socket)!=PR_SUCCESS) {
    print_nspr_error();

    return 1;
  }

  return (res?0:1);
}
