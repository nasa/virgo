#include "trick_units.hh"
#include <string>
#include <udunits2.h>
#include "map_trick_units_to_udunits.hh"
#include "UdUnits.hh"

static Trick::UdUnits trick_ud_units;

int initialize() {
    return trick_ud_units.read_default_xml();
}

static ut_unit *parse_units(const char *units)
{
    std::string units_str(units);
    units_str = map_trick_units_to_udunits(units_str);
    return ut_parse(Trick::UdUnits::get_u_system(),
                    units_str.c_str(),
                    UT_ASCII);
}

static cv_converter *get_converter(const char *from,
                                   const char *to)
{
    ut_unit *from_units = parse_units(from);
    if (!from_units) {
        return NULL;
    }

    ut_unit *to_units = parse_units(to);
    if (!to_units) {
        ut_free(from_units);
        return NULL;
    }

    cv_converter *converter = ut_get_converter(from_units, to_units);
    if (!converter) {
        ut_free(from_units);
        ut_free(to_units);
        return NULL;
    }

    ut_free(from_units);
    ut_free(to_units);

    return converter;
}

int convert_doubles(const double *input,
                    const size_t len,
                    const char *from,
                    const char *to,
                    double *output)
{
    cv_converter *converter = get_converter(from, to);
    if (!converter) {
        return -1;
    }

    cv_convert_doubles(converter, input, len, output);

    cv_free(converter);

    return 0;
}
