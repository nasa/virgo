.PHONY: all
all: libtrickunits.so

.PHONY: clean
clean:
	$(RM) libtrickunits.so

libtrickunits.so: map_trick_units_to_udunits.cpp \
				  map_trick_units_to_udunits.hh \
				  UdUnits.cpp \
				  UdUnits.hh \
				  trick_units.cpp \
				  trick_units.hh
	$(CXX) -shared -fPIC -o $@ $(CFLAGS) $(filter %.cpp,$^) -I/usr/include/udunits2 -ludunits2
