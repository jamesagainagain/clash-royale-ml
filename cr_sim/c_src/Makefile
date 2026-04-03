CC      = cc
CFLAGS  = -O2 -fPIC -Wall -Wextra -std=c11
LDFLAGS = -shared -lm

SRCS    = engine.c cards.c
OBJS    = $(SRCS:.c=.o)

# Platform detection
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
    LIB = ../libcr_engine.dylib
else
    LIB = ../libcr_engine.so
endif

all: $(LIB)

$(LIB): $(OBJS)
	$(CC) $(LDFLAGS) -o $@ $^

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJS) $(LIB)

.PHONY: all clean
