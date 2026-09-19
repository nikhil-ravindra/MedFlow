#include <stdio.h>
#include <time.h>

int main() {
    int day, month, year;
    int current_day, current_month, current_year;
    int age;

    printf("Enter your date of birth (DD MM YYYY): ");
    scanf("%d %d %d", &day, &month, &year);

    // Get today's date
    time_t t = time(NULL);
    struct tm today = *localtime(&t);

    current_day = today.tm_mday;
    current_month = today.tm_mon + 1;
    current_year = today.tm_year + 1900;

    // Calculate age
    age = current_year - year;

    // If birthday hasn't happened yet this year
    if (current_month < month ||
        (current_month == month && current_day < day)) {
        age--;
    }

    printf("Your age is: %d\n", age);

    return 0;
}