// Cell.h

#include "constants.h"
#include <array>
#include <vector>

enum CellType {
	FUEL,
	ROD,
	VOID
};

using CellPosXY = std::array<int, 2>;
using ResponseMatrix = std::vector<std::pair<&RectCell, float>>;

class RectCell {
private:
	CellType type;
	CellPosXY position;
	unsigned int fissionRate;
	ResponseMatrix responseMatrix;
	float temperature = INIT_TEMP;

public:
	RectCell(CellType _type, CellPosXY _position) :
		type(_type),
		position(_position) {}

	CellType getType() {
		return type;
	}
	CellPosXY getPosition() {
		return position;
	}
	unsigned int getFissionRate() {
		return fissionRate;
	}
	void setFissionRate(unsigned int _fissionRate)
	{
		fissionRate = _fissionRate;
	}
	void setResponseMatrix(ResponseMatrix _responseMatrix)
	{
		responseMatrix = _responseMatrix;
	}
	float getTemperature() {
	    return temperature;
	}
	void applyResponseMatrix();
}