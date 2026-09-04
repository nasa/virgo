#ifndef TRICK_UNITS_HH
#define TRICK_UNITS_HH

#include <cstddef>

extern "C" {
int initialize();

int convert_doubles(const double *input,
                    const size_t len,
                    const char *from,
                    const char *to,
                    double *output);
}

#endif
