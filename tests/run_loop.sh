#!/bin/bash
# A script used in loop-testing our main python test script.
# We have encountered issues with memory as test deconstruct
# and this scripts helps us regression test for non-determinism
# in the VIRGO or underlying VTK framework
# See also: https://discourse.vtk.org/t/looking-for-guidance-on-writing-python-unit-tests-using-python-vtk/16148/6

# --- Check for correct number of arguments ---
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <number_of_times_to_run>"
    exit 1
fi

# --- Get the loop count ---
LOOP_COUNT=$1
MYARGS="-t 10 --headless"

echo "Attempting to run test.py $MYARGS $LOOP_COUNT times..."

# --- Loop and execute ---
for i in $(seq 1 $LOOP_COUNT); do
    echo "=============== BASH LOOP $i of $LOOP_COUNT =================="
    # Execute the Python script
    ./test.py ${MYARGS}
    # Check the exit status of the previous command ($?)
    if [ $? -ne 0 ]; then
        echo "Error: returned a non-zero exit code (failure) on run $i."
        exit 1
    fi
done

echo "Success: ran successfully $LOOP_COUNT times."
exit 0
